"""
telegram_agent.py
-----------------
Envia cards de revisão humana ao Telegram para artigos com score >= 8
(needs_human_review=true) e atualiza o status para 'pending_review'.

Fluxo:
  1. Busca artigos com status='classified' AND needs_human_review=true
  2. Para cada artigo, monta card formatado + teclado inline
  3. Envia via Bot API (sendMessage)
  4. Atualiza status → 'pending_review' para os enviados
  5. Imprime relatório

Uso:
  python agents/telegram_agent.py
  python agents/telegram_agent.py --dry-run
  python agents/telegram_agent.py --limit 5
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("telegram")

# ── Constantes ────────────────────────────────────────────────────────────────

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
DEFAULT_LIMIT = 50

REQUIRED_ENV = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]


# ── Dataclass de relatório ────────────────────────────────────────────────────

@dataclass
class TelegramReport:
    total_fetched: int = 0
    sent: int = 0
    skipped_dry_run: int = 0
    errors: list[str] = field(default_factory=list)

    def print(self):
        print("\n" + "─" * 55)
        print("✅  Moderação via Telegram concluída")
        print("─" * 55)
        print(f"   Artigos para revisão:          {self.total_fetched:>4}")
        if self.skipped_dry_run:
            print(f"   Pulados (--dry-run):           {self.skipped_dry_run:>4}")
        else:
            print(f"   Cards enviados:                {self.sent:>4}")
        if self.errors:
            print(f"\n   ⚠️  Erros ({len(self.errors)}):")
            for e in self.errors:
                print(f"      • {e}")
        print(f"\n   Próximo passo: publish_agent.py")
        print("─" * 55 + "\n")


# ── Helpers de ambiente e banco ───────────────────────────────────────────────

def check_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        log.error(f"Variáveis de ambiente faltando: {', '.join(missing)}")
        sys.exit(1)


def fetch_review_pending(supabase: Client, limit: int) -> list[dict]:
    try:
        result = (
            supabase.table("raw_articles")
            .select(
                "id, headline_pt, summary_pt, score, score_breakdown, "
                "source_name, url, category"
            )
            .eq("status", "classified")
            .eq("needs_human_review", True)
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        log.error(f"Erro ao buscar artigos para revisão: {e}")
        return []


def mark_pending_review(supabase: Client, article_ids: list[str]) -> None:
    for aid in article_ids:
        try:
            supabase.table("raw_articles").update(
                {"status": "pending_review"}
            ).eq("id", aid).execute()
        except Exception as e:
            log.error(f"Erro ao atualizar status de {aid}: {e}")


# ── Construção do card e teclado ──────────────────────────────────────────────

def build_card(article: dict) -> str:
    score = article.get("score", "?")
    headline = article.get("headline_pt") or "(sem headline)"
    summary = article.get("summary_pt") or "(sem resumo)"
    category = article.get("category") or "?"
    source_name = article.get("source_name") or "?"
    source_url = article.get("url") or ""

    bd = article.get("score_breakdown") or {}
    precedent = bd.get("precedent", "?")
    velocity = bd.get("velocity", "?")
    inst_impact = bd.get("inst_impact", "?")
    system_reaction = bd.get("system_reaction", "?")

    lines = [
        f"🔴 REVISÃO NECESSÁRIA — Score {score}/10",
        "",
        f"📰 {headline}",
        "",
        "📋 RESUMO:",
        summary,
        "",
        "📊 BREAKDOWN:",
        f"Precedente: {precedent}/4 · Velocidade: {velocity}/2",
        f"Institucional: {inst_impact}/2 · Reação: {system_reaction}/2",
        "",
        f"🏷 Categoria: {category}",
        "",
        f"🔗 Fonte: {source_name}",
    ]
    if source_url:
        lines.append(source_url)

    return "\n".join(lines)


def build_keyboard(article_id: str) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Publicar", "callback_data": f"publish:{article_id}"},
            {"text": "❌ Rejeitar", "callback_data": f"reject:{article_id}"},
        ]]
    }


# ── Envio via Bot API ─────────────────────────────────────────────────────────

async def send_card(
    client: httpx.AsyncClient,
    article: dict,
    token: str,
    chat_id: str,
) -> bool:
    url = TELEGRAM_API.format(token=token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": build_card(article),
        "reply_markup": json.dumps(build_keyboard(article["id"])),
    }
    try:
        resp = await client.post(url, json=payload, timeout=10.0)
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            return True
        log.warning(
            f"Telegram rejeitou envio para {article['id']}: "
            f"status={resp.status_code} body={data}"
        )
        return False
    except Exception as e:
        log.error(f"Erro ao enviar card para {article['id']}: {e}")
        return False


# ── Orquestração principal ────────────────────────────────────────────────────

async def run(dry_run: bool = False, limit: int | None = None) -> TelegramReport:
    check_env()

    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    fetch_limit = limit if limit is not None else DEFAULT_LIMIT
    articles = fetch_review_pending(supabase, fetch_limit)
    report = TelegramReport(total_fetched=len(articles))

    if not articles:
        log.info("Nenhum artigo pendente de revisão humana.")
        report.print()
        return report

    log.info(f"Encontrados {len(articles)} artigos para revisão humana")

    sent_ids: list[str] = []

    async with httpx.AsyncClient() as client:
        for article in articles:
            aid = article["id"]

            if dry_run:
                log.info(f"[DRY RUN] Card para {aid} (score={article.get('score')}):")
                print(build_card(article))
                print(f"Teclado: {json.dumps(build_keyboard(aid), ensure_ascii=False)}")
                print()
                report.skipped_dry_run += 1
                continue

            success = await send_card(client, article, token, chat_id)
            if success:
                sent_ids.append(aid)
                report.sent += 1
                log.info(f"Card enviado: {aid} (score={article.get('score')})")
            else:
                report.errors.append(f"Falha ao enviar card para {aid}")

    if sent_ids and not dry_run:
        log.info(f"Marcando {len(sent_ids)} artigo(s) como pending_review...")
        mark_pending_review(supabase, sent_ids)

    report.print()
    return report


def main():
    parser = argparse.ArgumentParser(description="Trump Tracker — Telegram Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe cards sem enviar mensagens ao Telegram",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite máximo de artigos a processar (default: 50)",
    )
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
