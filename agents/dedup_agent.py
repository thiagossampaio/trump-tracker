"""
dedup_agent.py
--------------
Lê artigos raw_articles com status='classified' e needs_human_review=false,
gera embeddings via OpenAI text-embedding-3-small, consulta eventos similares
via pgvector, e roteia cada artigo pela tabela de decisão por similaridade cosine.

Fluxo (por artigo, em lote ordenado por source_tier ASC, published_at ASC):
  1a. Headline normalizada idêntica a artigo já aprovado no lote
      → rejected + duplicate_of_article_id (linhagem fechada pelo publish)
  1b. Headline normalizada idêntica a evento ativo recente (14d)
      → rejected + merged_into_id + enrich secondary_sources
  2.  Gera embedding (compartilhado via embedding_utils) e persiste em
      raw_articles.embedding — o publish reutiliza em vez de regenerar
  3.  Consulta events via RPC match_events (pgvector cosine distance):
      ≥ 0.92  → rejected (duplicata)
      0.80–0.91 → lógica update-vs-merge
      0.65–0.79 → approved + enrich secondary_sources do evento mais similar
      < 0.65  → approved (independente)
  4.  Compara contra artigos aprovados no MESMO lote (correção da cegueira
      intra-lote / syndication): ≥ 0.90 incondicional, ou ≥ 0.80 com mesma
      categoria → rejected + duplicate_of_article_id
  5.  Aprovado → entra no registro do lote; nunca deleta registros

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
from datetime import datetime, timedelta, timezone

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embedding_utils import (  # noqa: E402
    build_embedding_text,
    cosine_sim,
    generate_embedding,
    normalize_headline,
)

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

# Dedup intra-lote (artigos do MESMO ciclo, antes de virarem events):
# 0.80–0.89 exige mesma categoria; >= 0.90 rejeita incondicionalmente.
# Sem lógica de "evolução" aqui — cobertura do mesmo ciclo de 2h é
# simultânea, não evolução (a regra de update já exige > 2h de diferença).
BATCH_DUP_UNCONDITIONAL = 0.90

RECENT_HEADLINE_DAYS = 14   # janela do pré-filtro lexical contra events


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
    headline_match: int = 0   # headline idêntica a evento recente → rejected
    batch_duplicate: int = 0  # duplicata intra-lote → rejected
    errors: list[str] = field(default_factory=list)

    def print(self):
        total_approved = self.independent + self.related + self.updated + self.no_events
        total_rejected = self.duplicate + self.merged + self.headline_match + self.batch_duplicate
        print("\n" + "─" * 55)
        print("Deduplicação concluída")
        print("─" * 55)
        print(f"   Artigos processados:         {self.total_fetched:>4}")
        print(f"   Independentes (< 0.65):      {self.independent:>4}  → approved")
        print(f"   Relacionados (0.65–0.79):    {self.related:>4}  → approved + enrich")
        print(f"   Updates (0.80–0.91):         {self.updated:>4}  → approved")
        print(f"   Mesclados (0.80–0.91):       {self.merged:>4}  → rejected")
        print(f"   Duplicatas (≥ 0.92):         {self.duplicate:>4}  → rejected")
        print(f"   Headline = evento recente:   {self.headline_match:>4}  → rejected")
        print(f"   Duplicatas intra-lote:       {self.batch_duplicate:>4}  → rejected")
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
    Ordena por source_tier ASC, published_at ASC: o primeiro artigo
    aprovado de um grupo de syndication vira o canônico do lote
    (melhor fonte, mais antigo).
    """
    try:
        query = (
            supabase.table("raw_articles")
            .select("id, url, title, source_name, source_tier, headline_pt, summary_pt, category, published_at")
            .eq("status", "classified")
            .eq("needs_human_review", False)
            .order("source_tier", desc=False)
            .order("published_at", desc=False)
        )
        if limit is not None:
            query = query.limit(limit)
        result = query.execute()
        return result.data or []
    except Exception as e:
        log.error(f"Erro ao buscar artigos classified: {e}")
        return []


def fetch_recent_event_headlines(supabase: Client, days: int = RECENT_HEADLINE_DAYS) -> dict[str, str]:
    """
    Mapa {headline normalizada → event_id} dos eventos ativos dos últimos
    `days` dias. Pré-filtro lexical barato contra syndication: headline
    idêntica a evento recente → merge direto, sem custo de embedding.
    """
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            supabase.table("events")
            .select("id, headline")
            .is_("merged_into_id", "null")
            .gte("occurred_at", cutoff)
            .execute()
        )
        mapping: dict[str, str] = {}
        for row in result.data or []:
            hnorm = normalize_headline(row.get("headline"))
            if hnorm:
                mapping.setdefault(hnorm, row["id"])
        return mapping
    except Exception as e:
        log.warning(f"Erro ao buscar headlines de eventos recentes: {e}")
        return {}


# ── Consulta pgvector via RPC ─────────────────────────────────────────────────
# (geração de embedding agora vive em embedding_utils — compartilhada com publish)

def find_similar_events(supabase: Client, embedding: list[float]) -> list[dict]:
    """
    Chama a função SQL match_events via RPC do Supabase.
    Retorna até 10 eventos ordenados por distância cosine ascendente
    (margem de diagnóstico para grupos grandes de syndication).
    Cada item tem: id, slug, occurred_at, distance, similarity.
    Retorna [] se a tabela events estiver vazia ou em caso de erro.
    """
    try:
        result = supabase.rpc(
            "match_events",
            {"query_embedding": embedding, "match_count": 10},
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
    dedup_threshold: float = THRESH_DUPLICATE,
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

    if sim >= dedup_threshold:
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
    ref_id: str | None,
    dry_run: bool,
    embedding: list[float] | None = None,
) -> None:
    """
    Atualiza raw_articles conforme a decisão de dedup.
    Nunca deleta registros.

    ref_id: para rejected_merged é um event_id; para rejected_batch_duplicate
    é o id do artigo canônico do MESMO lote (raw_articles) — o publish_agent
    fecha a linhagem (merged_into_id) quando o canônico vira evento.

    embedding: quando fornecido, é persistido em raw_articles.embedding no
    mesmo UPDATE — o publish_agent reutiliza em vez de regenerar.
    """
    if action.startswith("approved"):
        payload: dict = {"status": "approved"}
    elif action == "rejected_merged":
        payload = {"status": "rejected", "merged_into_id": ref_id}
    elif action == "rejected_batch_duplicate":
        payload = {"status": "rejected", "duplicate_of_article_id": ref_id}
    else:  # rejected_duplicate
        payload = {"status": "rejected"}

    if embedding is not None:
        payload["embedding"] = embedding

    if dry_run:
        shown = {k: v for k, v in payload.items() if k != "embedding"}
        if embedding is not None:
            shown["embedding"] = f"<{len(embedding)} dims>"
        log.info(f"  [DRY RUN] article {article_id}: {action} → {shown}")
        return

    try:
        supabase.table("raw_articles").update(payload).eq("id", article_id).execute()
    except Exception as e:
        log.error(f"  Erro ao atualizar artigo {article_id}: {e}")
        raise


# ── Orquestração principal ────────────────────────────────────────────────────

async def run(dry_run: bool = False, limit: int | None = None, dedup_threshold: float = THRESH_DUPLICATE) -> DedupReport:
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

    # Pré-filtro lexical: headlines de eventos ativos recentes
    recent_headlines = fetch_recent_event_headlines(supabase)
    log.info(f"Headlines de eventos recentes ({RECENT_HEADLINE_DAYS}d): {len(recent_headlines)}")

    # Registro em memória dos artigos aprovados NESTE lote — corrige a
    # cegueira intra-lote (N cópias de syndication no mesmo ciclo, nenhuma
    # ainda em events, todas passavam como independentes).
    batch_approved: list[dict] = []

    for article in articles:
        aid = article["id"]
        label = (article.get("headline_pt") or article.get("title") or "")[:60]
        log.info(f"Processando {aid} — {label}")

        hnorm = normalize_headline(article.get("headline_pt"))

        # ── Fase 1a: headline idêntica a artigo já aprovado no lote ──────
        if hnorm:
            canon = next(
                (b for b in batch_approved if b["headline_norm"] == hnorm), None
            )
            if canon:
                log.info(
                    f"  → rejected_batch_duplicate (headline idêntica no lote)"
                    f" | canônico {canon['id']}"
                )
                try:
                    apply_decision(
                        supabase, aid, "rejected_batch_duplicate", canon["id"], dry_run
                    )
                except Exception as e:
                    report.errors.append(f"apply_decision falhou para {aid}: {e}")
                    continue
                report.batch_duplicate += 1
                continue

        # ── Fase 1b: headline idêntica a evento recente ───────────────────
        if hnorm and hnorm in recent_headlines:
            event_id = recent_headlines[hnorm]
            log.info(
                f"  → rejected_merged (headline idêntica a evento recente)"
                f" | evento {event_id}"
            )
            enrich_secondary_sources(supabase, event_id, article, dry_run)
            try:
                apply_decision(supabase, aid, "rejected_merged", event_id, dry_run)
            except Exception as e:
                report.errors.append(f"apply_decision falhou para {aid}: {e}")
                continue
            report.headline_match += 1
            continue

        # ── Fase 2: embedding (gerado uma vez, persistido p/ o publish) ──
        text = build_embedding_text(article)
        embedding = generate_embedding(openai_client, text)
        if embedding is None:
            # Permanece 'classified' — retry natural no próximo ciclo
            report.errors.append(f"Embedding falhou para {aid} — artigo pulado")
            continue

        # ── Fase 3: decisão contra events (pgvector) — vence o lote ──────
        similar_events = find_similar_events(supabase, embedding)
        action, ref_id = decide_action(article, similar_events, dedup_threshold)

        sim_info = ""
        if similar_events:
            sim_info = f" (sim={similar_events[0]['similarity']:.3f})"

        # ── Fase 4: decisão contra o lote (correção da falha raiz) ───────
        # Só se nenhum evento real rejeitou o artigo.
        if action.startswith("approved") and batch_approved:
            best_sim, best_batch = -1.0, None
            for b in batch_approved:
                s = cosine_sim(embedding, b["embedding"])
                if s > best_sim:
                    best_sim, best_batch = s, b
            same_cat = (
                best_batch is not None
                and best_batch["category"] == article.get("category")
            )
            if best_batch and (
                best_sim >= BATCH_DUP_UNCONDITIONAL
                or (best_sim >= THRESH_EPISODE_LO and same_cat)
            ):
                action, ref_id = "rejected_batch_duplicate", best_batch["id"]
                sim_info = f" (sim-lote={best_sim:.3f})"

        log.info(f"  → {action}{sim_info}" + (f" | ref {ref_id}" if ref_id else ""))

        # Enriquecer secondary_sources para artigos relacionados a evento real
        if action == "approved_related" and ref_id:
            enrich_secondary_sources(supabase, ref_id, article, dry_run)

        try:
            apply_decision(supabase, aid, action, ref_id, dry_run, embedding=embedding)
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
        elif action == "rejected_batch_duplicate":
            report.batch_duplicate += 1
            continue

        # ── Fase 5: aprovado — entra no registro do lote ──────────────────
        if action.startswith("approved"):
            batch_approved.append({
                "id": aid,
                "embedding": np.asarray(embedding, dtype=np.float32),
                "headline_norm": hnorm,
                "category": article.get("category"),
            })

    report.print()
    return report


def main():
    parser = argparse.ArgumentParser(description="Trump Tracker — Dedup Agent")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem gravar no banco")
    parser.add_argument("--limit", type=int, default=None, help="Limite de artigos a processar")
    parser.add_argument(
        "--dedup-threshold", type=float, default=THRESH_DUPLICATE,
        help=f"Threshold cosine para duplicatas (padrão {THRESH_DUPLICATE}; use 0.95 para backfill longo)",
    )
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit, dedup_threshold=args.dedup_threshold))


if __name__ == "__main__":
    main()
