"""
dedup_pending_review.py
-----------------------
Dedup SEMÂNTICO da fila de revisão humana (status='pending_review').

O dedup_agent padrão só processa 'classified' + needs_human_review=false.
Os artigos de score alto vão direto ao Telegram (pending_review) e nunca
passam por dedup — daí a fila inflada de duplicatas. Este script colapsa:

  Fase 1 (vs EVENTS publicados): se o artigo duplica um evento já no site
    → status='rejected', merged_into_id = event_id (não precisa revisão).
  Fase 2 (intra-fila): entre os sobreviventes, mantém um canônico por
    cluster (melhor tier, mais recente) e marca os demais
    → status='rejected', duplicate_of_article_id = canônico.

Sobreviventes permanecem 'pending_review' (com embedding salvo) para você
revisar no Telegram — agora sem duplicatas.

Critério (modo agressivo, configurável): sim ≥ 0.80 com MESMA categoria e
dentro de --window-hours; sim ≥ 0.92 dispensa a categoria.

Uso (do ambiente local, .env na raiz):
  python scripts/dedup_pending_review.py            # dry-run (default)
  python scripts/dedup_pending_review.py --apply
  Flags: --threshold 0.80 | --window-hours 96 | --no-category-guard
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "agents"))
from embedding_utils import (  # noqa: E402
    EMBEDDING_MODEL,
    build_embedding_text,
    normalize_headline,
    parse_vector,
)

load_dotenv(os.path.join(REPO_ROOT, ".env"))

PAGE_SIZE = 1000
UNCONDITIONAL = 0.92
EMBED_BATCH = 256


def parse_ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def fetch_paginated(supabase: Client, table: str, select: str, status_eq: str | None,
                    extra=None) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        q = supabase.table(table).select(select)
        if status_eq:
            q = q.eq("status", status_eq)
        if extra:
            q = extra(q)
        page = q.range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def embed_missing(openai_client: OpenAI, supabase: Client, rows: list[dict],
                  dry_run: bool) -> dict[str, np.ndarray]:
    """Gera (em lote) embeddings dos que não têm; persiste; retorna {id: vec}."""
    vecs: dict[str, np.ndarray] = {}
    todo: list[dict] = []
    for r in rows:
        v = parse_vector(r.get("embedding"))
        if v is not None:
            vecs[r["id"]] = np.asarray(v, dtype=np.float32)
        else:
            todo.append(r)

    if todo:
        print(f"   Gerando embedding de {len(todo)} artigo(s) (lotes de {EMBED_BATCH})...")
    for i in range(0, len(todo), EMBED_BATCH):
        chunk = todo[i : i + EMBED_BATCH]
        texts = [build_embedding_text(r) or "(vazio)" for r in chunk]
        resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        for r, item in zip(chunk, resp.data):
            emb = item.embedding
            vecs[r["id"]] = np.asarray(emb, dtype=np.float32)
            if not dry_run:
                supabase.table("raw_articles").update({"embedding": emb}).eq("id", r["id"]).execute()
    return vecs


def reject(supabase: Client, article_id: str, payload: dict, dry_run: bool) -> None:
    if dry_run:
        return
    supabase.table("raw_articles").update(payload).eq("id", article_id).execute()


def main():
    ap = argparse.ArgumentParser(description="Dedup semântico da fila pending_review")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--window-hours", type=float, default=96.0)
    ap.add_argument("--no-category-guard", action="store_true")
    args = ap.parse_args()
    dry_run = not args.apply
    window = args.window_hours * 3600
    guard = not args.no_category_guard

    for v in ("SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY"):
        if not os.getenv(v):
            print(f"❌ Falta variável: {v}")
            sys.exit(1)

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("📥 Carregando pending_review...")
    pend = fetch_paginated(
        supabase, "raw_articles",
        "id, headline_pt, summary_pt, category, score, source_tier, published_at, "
        "url, source_name, embedding",
        "pending_review",
    )
    print(f"   {len(pend)} artigos em pending_review")

    print("📥 Carregando events ativos (com embedding)...")
    events = fetch_paginated(
        supabase, "events",
        "id, headline, category, occurred_at, embedding",
        None,
        extra=lambda q: q.is_("merged_into_id", "null"),
    )
    ev = [e for e in events if parse_vector(e.get("embedding")) is not None]
    ev_vecs = np.array([parse_vector(e["embedding"]) for e in ev], dtype=np.float32)
    ev_vecs /= np.clip(np.linalg.norm(ev_vecs, axis=1, keepdims=True), 1e-9, None)
    ev_cat = [e.get("category") for e in ev]
    ev_ts = np.array([parse_ts(e.get("occurred_at")) for e in ev])
    print(f"   {len(ev)} eventos com embedding")

    print("🧮 Gerando/carregando embeddings da fila...")
    vecs = embed_missing(openai_client, supabase, pend, dry_run)

    # Ordena: melhor tier, mais recente primeiro → canônico natural
    pend.sort(key=lambda r: (r.get("source_tier") or 2, -parse_ts(r.get("published_at"))))

    rejected_vs_event = 0
    rejected_vs_batch = 0
    survivors: list[dict] = []          # canônicos mantidos (com vec normalizado)
    surv_vecs: list[np.ndarray] = []
    surv_cat: list[str] = []
    surv_ts: list[float] = []

    print("🔍 Deduplicando...")
    for r in pend:
        v = vecs.get(r["id"])
        if v is None:
            survivors.append(r); continue
        vn = v / max(float(np.linalg.norm(v)), 1e-9)
        ts = parse_ts(r.get("published_at"))
        cat = r.get("category")

        # ── Fase 1: vs EVENTS publicados ──
        if len(ev):
            sims = ev_vecs @ vn
            within = np.abs(ev_ts - ts) <= window
            best_i, best_s = -1, -1.0
            for i in np.argsort(-sims)[:10]:
                if not within[i]:
                    continue
                s = float(sims[i])
                ok = s >= UNCONDITIONAL or (s >= args.threshold and (not guard or ev_cat[i] == cat))
                if ok:
                    best_i, best_s = int(i), s
                    break
            if best_i >= 0:
                reject(supabase, r["id"],
                       {"status": "rejected", "merged_into_id": ev[best_i]["id"],
                        "embedding": v.tolist()}, dry_run)
                rejected_vs_event += 1
                continue

        # ── Fase 2: vs canônicos já mantidos no lote ──
        dup_of = None
        for j, sv in enumerate(surv_vecs):
            if abs(surv_ts[j] - ts) > window:
                continue
            s = float(np.dot(sv, vn))
            if s >= UNCONDITIONAL or (s >= args.threshold and (not guard or surv_cat[j] == cat)):
                dup_of = survivors[j]
                break
        if dup_of is not None:
            reject(supabase, r["id"],
                   {"status": "rejected", "duplicate_of_article_id": dup_of["id"],
                    "embedding": v.tolist()}, dry_run)
            rejected_vs_batch += 1
            continue

        # ── Sobrevivente: permanece pending_review ──
        survivors.append(r)
        surv_vecs.append(vn)
        surv_cat.append(cat)
        surv_ts.append(ts)

    print(f"\n{'═' * 64}")
    print(f"  Fila inicial:                 {len(pend):>5}")
    print(f"  Rejeitados (dup de evento):   {rejected_vs_event:>5}")
    print(f"  Rejeitados (dup intra-fila):  {rejected_vs_batch:>5}")
    print(f"  SOBREVIVENTES (p/ revisar):   {len(survivors):>5}")
    print(f"{'═' * 64}")

    surv_by_score: dict = {}
    for s in survivors:
        sc = s.get("score") or 0
        surv_by_score[sc] = surv_by_score.get(sc, 0) + 1
    print("  Sobreviventes por score:", dict(sorted(surv_by_score.items(), reverse=True)))

    if dry_run:
        print(f"\n  DRY-RUN — nada alterado. Use --apply para executar.\n")
    else:
        print(f"\n  ✅ Aplicado. {rejected_vs_event + rejected_vs_batch} artigos rejeitados, "
              f"{len(survivors)} mantidos em pending_review.\n")


if __name__ == "__main__":
    main()
