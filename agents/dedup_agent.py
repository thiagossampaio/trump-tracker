"""
dedup_agent.py
--------------
Lê artigos raw_articles com status='classified' e needs_human_review=false,
gera embeddings via OpenAI text-embedding-3-small, consulta eventos similares
via pgvector, e roteia cada artigo pela tabela de decisão por similaridade cosine.

Fluxo:
  1. Busca artigos classified + needs_human_review=false
  2. Gera embedding do texto "{headline_pt} {summary_pt} {category}"
  3. Consulta events via RPC match_events (pgvector cosine distance)
  4. Aplica tabela de decisão:
     ≥ 0.92  → rejected (duplicata)
     0.80–0.91 → lógica update-vs-merge
     0.65–0.79 → approved + enrich secondary_sources do evento mais similar
     < 0.65  → approved (independente)
  5. Atualiza raw_articles; nunca deleta registros

Uso:
  python agents/dedup_agent.py
  python agents/dedup_agent.py --dry-run
  python agents/dedup_agent.py --limit 20
  python agents/dedup_agent.py --dry-run --limit 5
"""

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dedup")

# ── Constantes ────────────────────────────────────────────────────────────────

REQUIRED_ENV = ["SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY"]

# Termos de evolução checados no título em inglês (não headline_pt)
EVOLUTION_TERMS = [
    "blocks", "responds", "reverses", "appeals",
    "rules", "overturns",
]

# Thresholds de similaridade (similarity = 1 - cosine_distance)
THRESH_DUPLICATE  = 0.92   # >= → duplicata incondicionada
THRESH_EPISODE_LO = 0.80   # faixa 0.80–0.91 → mesmo episódio
THRESH_RELATED_LO = 0.65   # faixa 0.65–0.79 → relacionado
# < 0.65 → independente

UPDATE_HOURS_MIN = 2        # artigo deve ser > 2h mais novo que o evento para ser update


# ── Dataclass de relatório ────────────────────────────────────────────────────

@dataclass
class DedupReport:
    total_fetched: int = 0
    independent: int = 0    # < 0.65 → approved
    related: int = 0        # 0.65–0.79 → approved + enrich
    updated: int = 0        # 0.80–0.91 + evolução → approved
    merged: int = 0         # 0.80–0.91 + sem evolução → rejected
    duplicate: int = 0      # >= 0.92 → rejected
    no_events: int = 0      # tabela events vazia → approved
    errors: list[str] = field(default_factory=list)

    def print(self):
        total_approved = self.independent + self.related + self.updated + self.no_events
        total_rejected = self.duplicate + self.merged
        print("\n" + "─" * 55)
        print("Deduplicação concluída")
        print("─" * 55)
        print(f"   Artigos processados:         {self.total_fetched:>4}")
        print(f"   Independentes (< 0.65):      {self.independent:>4}  → approved")
        print(f"   Relacionados (0.65–0.79):    {self.related:>4}  → approved + enrich")
        print(f"   Updates (0.80–0.91):         {self.updated:>4}  → approved")
        print(f"   Mesclados (0.80–0.91):       {self.merged:>4}  → rejected")
        print(f"   Duplicatas (≥ 0.92):         {self.duplicate:>4}  → rejected")
        print(f"   Sem eventos (tabela vazia):  {self.no_events:>4}  → approved")
        print(f"\n   Total aprovados:             {total_approved:>4}")
        print(f"   Total rejeitados:            {total_rejected:>4}")
        if self.errors:
            print(f"\n   ⚠️  Erros ({len(self.errors)}):")
            for e in self.errors:
                print(f"      • {e}")
        print(f"\n   Próximo passo: publish_agent.py")
        print("─" * 55 + "\n")


# ── Ambiente e banco ──────────────────────────────────────────────────────────

def check_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        log.error(f"Variáveis de ambiente faltando: {', '.join(missing)}")
        sys.exit(1)


def fetch_classified_articles(supabase: Client, limit: int | None) -> list[dict]:
    """
    Busca artigos com status='classified' e needs_human_review=false.
    Inclui 'title' (inglês) necessário para checar EVOLUTION_TERMS.
    Ordena por published_at ASC para processar mais antigos primeiro.
    """
    try:
        query = (
            supabase.table("raw_articles")
            .select("id, url, title, source_name, source_tier, headline_pt, summary_pt, category, published_at")
            .eq("status", "classified")
            .eq("needs_human_review", False)
            .order("published_at", desc=False)
        )
        if limit is not None:
            query = query.limit(limit)
        result = query.execute()
        return result.data or []
    except Exception as e:
        log.error(f"Erro ao buscar artigos classified: {e}")
        return []


# ── Geração de embeddings ─────────────────────────────────────────────────────

def generate_embedding(openai_client: OpenAI, text: str) -> list[float] | None:
    """Gera embedding de 1536 dimensões via text-embedding-3-small."""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        log.warning(f"OpenAI: erro ao gerar embedding — {e}")
        return None


# ── Consulta pgvector via RPC ─────────────────────────────────────────────────

def find_similar_events(supabase: Client, embedding: list[float]) -> list[dict]:
    """
    Chama a função SQL match_events via RPC do Supabase.
    Retorna até 5 eventos ordenados por distância cosine ascendente.
    Cada item tem: id, slug, occurred_at, distance, similarity.
    Retorna [] se a tabela events estiver vazia ou em caso de erro.
    """
    try:
        result = supabase.rpc(
            "match_events",
            {"query_embedding": embedding, "match_count": 5},
        ).execute()
        return result.data or []
    except Exception as e:
        log.warning(f"pgvector RPC erro: {e}")
        return []


# ── Lógica de decisão ─────────────────────────────────────────────────────────

def has_evolution_term(title: str) -> bool:
    """Checa termos de evolução no título original em inglês."""
    t = title.lower()
    return any(term in t for term in EVOLUTION_TERMS)


def hours_diff(article_published_at: str, event_occurred_at: str) -> float:
    """
    Retorna (article - event) em horas.
    Positivo = artigo é mais novo que o evento.
    """
    def parse_iso(s: str) -> datetime:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    return (parse_iso(article_published_at) - parse_iso(event_occurred_at)).total_seconds() / 3600


def decide_action(
    article: dict,
    similar_events: list[dict],
) -> tuple[str, str | None]:
    """
    Aplica tabela de decisão por similaridade cosine.

    Retorna (action, event_id) onde:
      action ∈ {
        "approved_independent",   # < 0.65 ou tabela vazia
        "approved_related",       # 0.65–0.79 (enriquece secondary_sources)
        "approved_update",        # 0.80–0.91 + > 2h + termo de evolução
        "rejected_duplicate",     # >= 0.92
        "rejected_merged",        # 0.80–0.91 sem critério de update
      }
      event_id: UUID do evento mais similar (None para independente/vazio)
    """
    # Tabela events vazia — sem comparação possível
    if not similar_events:
        return "approved_independent", None

    best = similar_events[0]
    sim = best["similarity"]  # pré-calculado pelo SQL: 1 - cosine_distance

    if sim >= THRESH_DUPLICATE:
        # Duplicata incondicional
        return "rejected_duplicate", best["id"]

    if sim >= THRESH_EPISODE_LO:
        # Mesmo episódio — lógica update vs. merge
        diff = hours_diff(article["published_at"], best["occurred_at"])
        has_evo = has_evolution_term(article.get("title", "") or "")

        if diff > UPDATE_HOURS_MIN and has_evo:
            return "approved_update", best["id"]
        else:
            return "rejected_merged", best["id"]

    if sim >= THRESH_RELATED_LO:
        # Relacionado — publicar separado e enriquecer secondary_sources
        return "approved_related", best["id"]

    # Verdadeiramente independente
    return "approved_independent", None


# ── Enriquecimento de fontes secundárias ─────────────────────────────────────

def enrich_secondary_sources(
    supabase: Client,
    event_id: str,
    article: dict,
    dry_run: bool,
) -> None:
    """
    Adiciona a URL do artigo ao array JSONB secondary_sources do evento,
    deduplicando por URL antes de atualizar.
    """
    try:
        result = (
            supabase.table("events")
            .select("secondary_sources")
            .eq("id", event_id)
            .single()
            .execute()
        )
        current = result.data.get("secondary_sources") or []

        new_entry = {
            "url":  article["url"],
            "name": article.get("source_name", ""),
            "tier": article.get("source_tier", 2),
        }

        # Dedup por URL
        if any(s.get("url") == new_entry["url"] for s in current):
            log.info(f"  secondary_sources: URL já presente no evento {event_id}, pulando")
            return

        updated = current + [new_entry]

        if dry_run:
            log.info(f"  [DRY RUN] Would enrich evento {event_id} com {new_entry['name']}: {new_entry['url']}")
            return

        supabase.table("events").update({"secondary_sources": updated}).eq("id", event_id).execute()
        log.info(f"  Enriquecido evento {event_id} com fonte: {new_entry['name']}")

    except Exception as e:
        log.warning(f"  Erro ao enriquecer secondary_sources de {event_id}: {e}")


# ── Aplicação da decisão no banco ────────────────────────────────────────────

def apply_decision(
    supabase: Client,
    article_id: str,
    action: str,
    event_id: str | None,
    dry_run: bool,
) -> None:
    """
    Atualiza raw_articles conforme a decisão de dedup.
    Nunca deleta registros.
    """
    if action.startswith("approved"):
        payload: dict = {"status": "approved"}
    elif action == "rejected_merged":
        payload = {"status": "rejected", "merged_into_id": event_id}
    else:  # rejected_duplicate
        payload = {"status": "rejected"}

    if dry_run:
        log.info(f"  [DRY RUN] article {article_id}: {action} → {payload}")
        return

    try:
        supabase.table("raw_articles").update(payload).eq("id", article_id).execute()
    except Exception as e:
        log.error(f"  Erro ao atualizar artigo {article_id}: {e}")
        raise


# ── Orquestração principal ────────────────────────────────────────────────────

async def run(dry_run: bool = False, limit: int | None = None) -> DedupReport:
    check_env()

    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    articles = fetch_classified_articles(supabase, limit)
    report = DedupReport(total_fetched=len(articles))

    if not articles:
        log.info("Nenhum artigo classified encontrado.")
        report.print()
        return report

    log.info(f"Encontrados {len(articles)} artigos classified — iniciando dedup")

    for article in articles:
        aid = article["id"]
        label = (article.get("headline_pt") or article.get("title") or "")[:60]
        log.info(f"Processando {aid} — {label}")

        # Texto para embedding: headline_pt + summary_pt + category
        text = " ".join(filter(None, [
            article.get("headline_pt", ""),
            article.get("summary_pt", ""),
            article.get("category", ""),
        ])).strip()

        embedding = generate_embedding(openai_client, text)
        if embedding is None:
            report.errors.append(f"Embedding falhou para {aid} — artigo pulado")
            continue

        similar_events = find_similar_events(supabase, embedding)
        action, event_id = decide_action(article, similar_events)

        sim_info = ""
        if similar_events:
            sim_info = f" (sim={similar_events[0]['similarity']:.3f})"
        log.info(f"  → {action}{sim_info}" + (f" | evento {event_id}" if event_id else ""))

        # Enriquecer secondary_sources para artigos relacionados
        if action == "approved_related" and event_id:
            enrich_secondary_sources(supabase, event_id, article, dry_run)

        try:
            apply_decision(supabase, aid, action, event_id, dry_run)
        except Exception as e:
            report.errors.append(f"apply_decision falhou para {aid}: {e}")
            continue

        # Atualizar contadores
        if action == "approved_independent":
            if not similar_events:
                report.no_events += 1
            else:
                report.independent += 1
        elif action == "approved_related":
            report.related += 1
        elif action == "approved_update":
            report.updated += 1
        elif action == "rejected_merged":
            report.merged += 1
        elif action == "rejected_duplicate":
            report.duplicate += 1

    report.print()
    return report


def main():
    parser = argparse.ArgumentParser(description="Trump Tracker — Dedup Agent")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem gravar no banco")
    parser.add_argument("--limit", type=int, default=None, help="Limite de artigos a processar")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
