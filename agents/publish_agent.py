"""
publish_agent.py
----------------
Transforma artigos aprovados (approved ou approved_manual) em eventos
públicos na tabela events, gerando embedding final, slug único e
disparando revalidação do cache Next.js.

Fluxo:
  1. Busca artigos com status IN ('approved', 'approved_manual')
  2. Para cada artigo:
     a. Gera embedding via text-embedding-3-small
     b. Gera slug único (kebab + data, anti-colisão numérica)
     c. Insere na tabela events (ON CONFLICT slug → pula)
     d. Atualiza raw_articles.status = 'published'
  3. Dispara POST /api/revalidate para atualizar o cache do feed
  4. Imprime relatório

Uso:
  python agents/publish_agent.py
  python agents/publish_agent.py --dry-run
  python agents/publish_agent.py --limit 10
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client
from unidecode import unidecode

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("publish")

# ── Constantes ────────────────────────────────────────────────────────────────

DEFAULT_LIMIT = 50
EMBEDDING_MODEL = "text-embedding-3-small"

REQUIRED_ENV = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "OPENAI_API_KEY",
    "NEXT_PUBLIC_SITE_URL",
    "REVALIDATE_SECRET",
]


# ── Dataclass de relatório ────────────────────────────────────────────────────

@dataclass
class PublishReport:
    total_fetched: int = 0
    published: int = 0
    conflicts_ignored: int = 0
    skipped_dry_run: int = 0
    errors: list[str] = field(default_factory=list)

    def print(self):
        site = os.getenv("NEXT_PUBLIC_SITE_URL", "")
        print("\n" + "─" * 55)
        print("✅  Publicação concluída")
        print("─" * 55)
        print(f"   Artigos aprovados:             {self.total_fetched:>4}")
        if self.skipped_dry_run:
            print(f"   Pulados (--dry-run):           {self.skipped_dry_run:>4}")
        else:
            print(f"   Eventos publicados:            {self.published:>4}")
            print(f"   Conflitos ignorados (slug):    {self.conflicts_ignored:>4}")
        if self.errors:
            print(f"\n   ⚠️  Erros ({len(self.errors)}):")
            for e in self.errors:
                print(f"      • {e}")
        if site:
            print(f"\n   Feed: {site}")
        print("─" * 55 + "\n")


# ── Helpers de ambiente e banco ───────────────────────────────────────────────

def check_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        log.error(f"Variáveis de ambiente faltando: {', '.join(missing)}")
        sys.exit(1)


def fetch_approved(supabase: Client, limit: int) -> list[dict]:
    try:
        result = (
            supabase.table("raw_articles")
            .select(
                "id, url, headline_pt, summary_pt, historical_context, "
                "score, score_breakdown, category, confidence, "
                "source_name, source_tier, published_at, status"
            )
            .in_("status", ["approved", "approved_manual"])
            .order("published_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        log.error(f"Erro ao buscar artigos aprovados: {e}")
        return []


def mark_published(supabase: Client, article_id: str) -> None:
    try:
        supabase.table("raw_articles").update(
            {"status": "published"}
        ).eq("id", article_id).execute()
    except Exception as e:
        log.error(f"Erro ao marcar {article_id} como published: {e}")


# ── Embedding ─────────────────────────────────────────────────────────────────

def generate_embedding(openai_client: OpenAI, article: dict) -> list[float] | None:
    """Gera embedding de 1536 dimensões via text-embedding-3-small."""
    text = " ".join(filter(None, [
        article.get("headline_pt"),
        article.get("summary_pt"),
        article.get("category"),
    ]))
    try:
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        log.warning(f"OpenAI: erro ao gerar embedding — {e}")
        return None


# ── Slug ──────────────────────────────────────────────────────────────────────

def parse_dt(iso_str: str | None) -> datetime:
    if not iso_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def generate_slug(headline_pt: str, occurred_at: datetime, supabase: Client) -> str:
    """Gera slug kebab único: {base}-{YYYY-MM-DD}[-N]."""
    base = re.sub(r"[^a-z0-9]+", "-", unidecode(headline_pt).lower()).strip("-")[:60]
    date_str = occurred_at.strftime("%Y-%m-%d")
    slug = f"{base}-{date_str}"

    candidate = slug
    counter = 2
    while True:
        exists = (
            supabase.table("events")
            .select("id")
            .eq("slug", candidate)
            .execute()
        )
        if not exists.data:
            return candidate
        candidate = f"{slug}-{counter}"
        counter += 1


# ── Construção e inserção do evento ──────────────────────────────────────────

def build_event_row(article: dict, embedding: list[float], slug: str) -> dict:
    review_status = (
        "human_approved" if article["status"] == "approved_manual" else "auto"
    )
    return {
        "slug": slug,
        "headline": article.get("headline_pt"),
        "summary": article.get("summary_pt"),
        "historical_context": article.get("historical_context"),
        "score": article.get("score"),
        "score_breakdown": article.get("score_breakdown"),
        "category": article.get("category"),
        "confidence": article.get("confidence"),
        "source_url": article.get("url"),
        "source_name": article.get("source_name"),
        "source_tier": article.get("source_tier"),
        "occurred_at": article.get("published_at"),
        "review_status": review_status,
        "raw_article_id": article.get("id"),
        "embedding": embedding,
        "tags": [],
        "secondary_sources": [],
    }


def insert_event(supabase: Client, row: dict) -> str:
    """
    Insere evento na tabela events.
    Retorna 'inserted' em sucesso ou 'conflict' se slug já existir.
    """
    try:
        supabase.table("events").insert(row).execute()
        return "inserted"
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            log.info(f"Slug já existe: {row['slug']} — evento ignorado")
            return "conflict"
        log.error(f"Erro ao inserir evento {row['slug']}: {e}")
        raise


# ── Revalidação de cache Next.js ──────────────────────────────────────────────

async def trigger_revalidation(client: httpx.AsyncClient) -> None:
    url = f"{os.environ['NEXT_PUBLIC_SITE_URL']}/api/revalidate"
    headers = {"Authorization": f"Bearer {os.environ['REVALIDATE_SECRET']}"}
    try:
        resp = await client.post(
            url,
            json={"tags": ["events-feed"]},
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code == 200:
            log.info("Cache revalidado com sucesso")
        else:
            log.warning(f"Revalidação retornou status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log.warning(f"Falha ao revalidar cache (pipeline continua): {e}")


# ── Orquestração principal ────────────────────────────────────────────────────

async def run(dry_run: bool = False, limit: int | None = None) -> PublishReport:
    check_env()

    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    fetch_limit = limit if limit is not None else DEFAULT_LIMIT
    articles = fetch_approved(supabase, fetch_limit)
    report = PublishReport(total_fetched=len(articles))

    if not articles:
        log.info("Nenhum artigo aprovado encontrado.")
        report.print()
        return report

    log.info(f"Encontrados {len(articles)} artigos aprovados — publicando...")

    async with httpx.AsyncClient() as http_client:
        for article in articles:
            aid = article["id"]

            embedding = generate_embedding(openai_client, article)
            if embedding is None:
                report.errors.append(f"Embedding falhou para {aid}")
                continue

            occurred_at = parse_dt(article.get("published_at"))
            slug = generate_slug(
                article.get("headline_pt") or aid,
                occurred_at,
                supabase,
            )

            row = build_event_row(article, embedding, slug)

            if dry_run:
                log.info(
                    f"[DRY RUN] Evento para {aid}: "
                    f"slug={slug}, score={article.get('score')}, "
                    f"review_status={row['review_status']}"
                )
                report.skipped_dry_run += 1
                continue

            try:
                outcome = insert_event(supabase, row)
            except Exception as e:
                report.errors.append(f"Erro ao inserir {aid}: {e}")
                continue

            if outcome == "inserted":
                report.published += 1
                log.info(f"Evento publicado: {slug} (score={article.get('score')})")
            else:
                report.conflicts_ignored += 1

            # Marca o artigo como publicado mesmo em caso de conflito de slug
            # (idempotência: re-execução não duplica eventos)
            mark_published(supabase, aid)

        if not dry_run and report.published > 0:
            log.info("Disparando revalidação do cache Next.js...")
            await trigger_revalidation(http_client)

    report.print()
    return report


def main():
    parser = argparse.ArgumentParser(description="Trump Tracker — Publish Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa sem gravar no banco nem revalidar cache",
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
