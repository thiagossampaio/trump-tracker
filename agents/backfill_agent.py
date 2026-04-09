"""
backfill_agent.py
-----------------
Processa eventos históricos de Trump desde a posse (20/jan/2025),
dividindo o período em janelas diárias e adaptando as fontes por estratégia.

Estratégias por período:
  short  (≤ 60 dias)  — NewsAPI + GDELT + Guardian + RSS
  medium (≤ 365 dias) — GDELT + Guardian + RSS
  long   (> 365 dias) — GDELT + Guardian + Wikipedia (sem RSS)

Uso:
  python agents/backfill_agent.py --from 2025-01-20 --to 2025-02-20 --dry-run
  python agents/backfill_agent.py --from 2025-01-20
  python agents/backfill_agent.py --from 2025-01-20 --batch-size 14
"""

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

# ── Resolve módulo irmão ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest_agent import (  # noqa: E402
    RawArticle,
    dedup_against_db,
    fetch_gdelt,
    fetch_guardian,
    fetch_newsapi,
    fetch_rss,
    gdelt_datetime,
    insert_articles,
    is_high_priority,
    is_relevant,
    load_config,
    parse_datetime,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill")

REQUIRED_ENV = ["SUPABASE_URL", "SUPABASE_KEY"]
INAUGURATION_DATE = date(2025, 1, 20)

# RSS feeds só têm itens recentes — não útil para datas mais antigas que isso.
RSS_MAX_LOOKBACK_DAYS = 7


# ── Dataclass de relatório ────────────────────────────────────────────────────

@dataclass
class BackfillReport:
    from_date: date = INAUGURATION_DATE
    to_date: date = INAUGURATION_DATE
    strategy: str = "short"
    windows_total: int = 0
    windows_processed: int = 0
    inserted: int = 0
    already_in_db: int = 0
    errors: list[str] = field(default_factory=list)

    def print(self):
        days = (self.to_date - self.from_date).days + 1
        print("\n" + "─" * 55)
        print("✅  Backfill concluído")
        print("─" * 55)
        print(f"   Período:            {self.from_date} → {self.to_date} ({days} dias)")
        print(f"   Estratégia:         {self.strategy}")
        print(f"   Janelas:            {self.windows_processed}/{self.windows_total}")
        print(f"   Artigos inseridos:  {self.inserted:>6}")
        print(f"   Já no banco:        {self.already_in_db:>6}")
        if self.errors:
            print(f"\n   ⚠️  Erros ({len(self.errors)}):")
            for e in self.errors[:10]:
                print(f"      • {e}")
        if self.strategy == "long":
            print(f"\n   ⚠️  Estratégia 'long': rode dedup com threshold conservador:")
            print(f"      python agents/dedup_agent.py --dedup-threshold 0.95")
        print(f"\n   Próximo passo: classify_agent.py")
        print("─" * 55 + "\n")


# ── Estratégia ────────────────────────────────────────────────────────────────

def determine_strategy(from_date: date, to_date: date) -> str:
    days = (to_date - from_date).days
    if days <= 60:
        return "short"
    if days <= 365:
        return "medium"
    return "long"


# ── Janelas diárias ───────────────────────────────────────────────────────────

def generate_daily_windows(
    from_date: date,
    to_date: date,
) -> list[tuple[datetime, datetime]]:
    """Divide o período em janelas de 24h (UTC), do mais antigo para o mais recente."""
    windows = []
    current = from_date
    while current <= to_date:
        start = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        windows.append((start, end))
        current += timedelta(days=1)
    return windows


# ── Wikipedia (estratégia 'long') ─────────────────────────────────────────────

async def fetch_wikipedia_anchors(
    client: httpx.AsyncClient,
    window_date: datetime,
) -> list[RawArticle]:
    """Busca artigos do Wikipedia relacionados a Trump na data da janela."""
    date_str = window_date.strftime("%Y-%m-%d")
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"Trump {date_str}",
        "srlimit": 10,
        "format": "json",
    }
    try:
        r = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"Wikipedia: erro para {date_str} — {e}")
        return []

    articles = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        pageid = item.get("pageid")
        if not title or not pageid:
            continue
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
        articles.append(RawArticle(
            url=url,
            title=title,
            body=snippet[:2000],
            source_name="Wikipedia",
            source_tier=2,
            published_at=window_date,
            raw_query=f"Trump {date_str}",
            priority=is_high_priority(title),
        ))

    log.info(f"Wikipedia [{date_str}]: {len(articles)} artigos")
    return articles


# ── Processamento de uma janela ───────────────────────────────────────────────

async def process_window(
    client: httpx.AsyncClient,
    supabase: Client,
    config: dict,
    window_start: datetime,
    window_end: datetime,
    strategy: str,
    dry_run: bool,
) -> tuple[int, int, list[str]]:
    """
    Processa uma janela de 24h.
    Retorna (inserted, already_in_db, errors).
    """
    queries = config.get("queries", {}).get("primary", [])
    all_articles: list[RawArticle] = []
    errors: list[str] = []

    tasks: dict[str, asyncio.Task] = {}

    # NewsAPI: só na estratégia "short" (free tier suporta até 1 mês de lookback)
    if strategy == "short" and os.getenv("NEWSAPI_KEY"):
        tasks["newsapi"] = asyncio.create_task(
            fetch_newsapi(client, queries, window_start, os.environ["NEWSAPI_KEY"])
        )

    # GDELT: todas as estratégias
    tasks["gdelt"] = asyncio.create_task(
        fetch_gdelt(client, queries, window_start)
    )

    # Guardian: todas as estratégias (se chave disponível)
    if os.getenv("GUARDIAN_API_KEY"):
        tasks["guardian"] = asyncio.create_task(
            fetch_guardian(client, queries, window_start, os.environ["GUARDIAN_API_KEY"])
        )

    # RSS: apenas se a janela for recente (feeds só têm itens dos últimos dias)
    days_ago = (datetime.now(timezone.utc) - window_start).days
    if strategy in ("short", "medium") and days_ago <= RSS_MAX_LOOKBACK_DAYS:
        rss_feeds = config.get("rss_feeds", [])
        if rss_feeds:
            tasks["rss"] = asyncio.create_task(
                fetch_rss(client, rss_feeds, window_start)
            )

    # Wikipedia: apenas estratégia "long"
    if strategy == "long":
        tasks["wikipedia"] = asyncio.create_task(
            fetch_wikipedia_anchors(client, window_start)
        )

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for name, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            msg = f"{window_start.date()} [{name}]: {result}"
            log.warning(msg)
            errors.append(msg)
        else:
            # Filtrar artigos fora da janela (published_at < window_end)
            in_window = [a for a in result if a.published_at < window_end]
            relevant = [a for a in in_window if is_relevant(a.title)]
            all_articles.extend(relevant)

    new_articles, already_in_db = dedup_against_db(all_articles, supabase)
    inserted, insert_errors = insert_articles(new_articles, supabase, dry_run=dry_run)
    errors.extend(insert_errors)

    return inserted, already_in_db, errors


# ── Orquestração ──────────────────────────────────────────────────────────────

async def run(
    from_date: date,
    to_date: date,
    batch_size: int = 7,
    dry_run: bool = False,
) -> BackfillReport:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        log.error(f"Variáveis de ambiente faltando: {', '.join(missing)}")
        sys.exit(1)

    config = load_config()
    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )

    strategy = determine_strategy(from_date, to_date)
    windows = generate_daily_windows(from_date, to_date)

    report = BackfillReport(
        from_date=from_date,
        to_date=to_date,
        strategy=strategy,
        windows_total=len(windows),
    )

    log.info(f"Backfill: {from_date} → {to_date} | {len(windows)} janelas | estratégia={strategy}")
    if dry_run:
        log.info("[DRY RUN] Nenhuma escrita no banco.")
    if strategy == "long":
        log.info("Estratégia 'long': Wikipedia ativado. Use --dedup-threshold 0.95 no dedup_agent.")

    async with httpx.AsyncClient(
        headers={"User-Agent": "TrumpTracker/1.0 (backfill)"},
        follow_redirects=True,
    ) as client:
        for i, (window_start, window_end) in enumerate(windows):
            inserted, already_in_db, errors = await process_window(
                client, supabase, config,
                window_start, window_end,
                strategy, dry_run,
            )
            report.windows_processed += 1
            report.inserted += inserted
            report.already_in_db += already_in_db
            report.errors.extend(errors)

            print(
                f"[{i + 1:>3}/{len(windows)}] {window_start.date()} "
                f"| +{inserted} inseridos | {already_in_db} já no banco"
                + (" [DRY RUN]" if dry_run else "")
            )

            # Pausa entre lotes para não sobrecarregar as APIs
            if (i + 1) % batch_size == 0 and (i + 1) < len(windows):
                log.info(f"Lote concluído ({batch_size} janelas). Aguardando 2s...")
                await asyncio.sleep(2)

    report.print()
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Trump Tracker — Backfill Histórico",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python agents/backfill_agent.py --from 2025-01-20 --to 2025-02-20 --dry-run
  python agents/backfill_agent.py --from 2025-01-20  # até hoje
  python agents/backfill_agent.py --from 2025-01-20 --batch-size 14
        """,
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Data de início (mínimo: 2025-01-20, posse de Trump)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Data de fim (padrão: hoje)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=7,
        help="Número de janelas diárias por lote antes de uma pausa (padrão: 7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa sem gravar no banco",
    )
    args = parser.parse_args()

    try:
        from_date = date.fromisoformat(args.from_date)
    except ValueError:
        parser.error(f"--from: formato inválido '{args.from_date}'. Use YYYY-MM-DD.")

    if from_date < INAUGURATION_DATE:
        parser.error(f"--from não pode ser anterior à posse: {INAUGURATION_DATE}")

    to_date = date.today()
    if args.to_date:
        try:
            to_date = date.fromisoformat(args.to_date)
        except ValueError:
            parser.error(f"--to: formato inválido '{args.to_date}'. Use YYYY-MM-DD.")

    if to_date < from_date:
        parser.error("--to deve ser posterior a --from.")

    asyncio.run(run(
        from_date=from_date,
        to_date=to_date,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
