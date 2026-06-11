"""
cleanup_duplicates.py
---------------------
Higienização da tabela events: encontra eventos duplicados já publicados
(syndication que passou pelo dedup antigo) e aplica soft-merge — seta
merged_into_id do duplicado apontando para o evento canônico. O site já
filtra merged_into_id IS NULL, então os duplicados somem do feed
imediatamente; nada é deletado (reversível e auditável).

Clusterização por union-find sobre duas fontes de arestas:
  - Semântica: similaridade de cosseno >= --threshold (default 0.80) entre
    embeddings, exigindo mesma categoria (dispensada se sim >= 0.92) e
    janela temporal de --max-window-hours (default 72h)
  - Lexical: headline normalizada idêntica (mesma janela temporal)

Canônico por cluster: menor source_tier → occurred_at mais antigo →
maior view_count → menor created_at.

Uso (do ambiente local, com .env na raiz do repo):
  python scripts/cleanup_duplicates.py                     # dry-run (default)
  python scripts/cleanup_duplicates.py --apply             # executa merges
  python scripts/cleanup_duplicates.py --apply --revalidate
  Flags: --threshold 0.80 | --max-window-hours 72 | --no-category-guard
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import httpx
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "agents"))
from embedding_utils import (  # noqa: E402
    build_embedding_text,
    generate_embedding,
    normalize_headline,
    parse_vector,
)

load_dotenv(os.path.join(REPO_ROOT, ".env"))

THRESH_UNCONDITIONAL = 0.92   # dispensa o guard de categoria
PAGE_SIZE = 1000              # limite do PostgREST por request
CLUSTER_SPAN_WARN_DAYS = 7


# ── Download ──────────────────────────────────────────────────────────────────

def fetch_active_events(supabase: Client) -> list[dict]:
    """Baixa todos os events ativos (merged_into_id IS NULL), paginado."""
    fields = (
        "id, slug, headline, summary, category, occurred_at, created_at, "
        "source_url, source_name, source_tier, secondary_sources, "
        "view_count, embedding"
    )
    events: list[dict] = []
    offset = 0
    while True:
        page = (
            supabase.table("events")
            .select(fields)
            .is_("merged_into_id", "null")
            .order("occurred_at", desc=False)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        ).data or []
        events.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return events


# ── Backfill de embeddings faltantes ──────────────────────────────────────────

def backfill_embeddings(
    supabase: Client, openai_client: OpenAI, events: list[dict]
) -> tuple[int, int]:
    """
    Gera e grava embeddings para events sem embedding. Roda mesmo em
    dry-run: é correção de dado (não merge) e o clustering precisa deles.
    Retorna (corrigidos, falhas).
    """
    missing = [e for e in events if parse_vector(e.get("embedding")) is None]
    if not missing:
        return 0, 0

    print(f"⚙️  Backfill: {len(missing)} evento(s) sem embedding")
    fixed = failed = 0
    for ev in missing:
        text = build_embedding_text({
            "headline_pt": ev.get("headline"),
            "summary_pt": ev.get("summary"),
            "category": ev.get("category"),
        })
        emb = generate_embedding(openai_client, text)
        if emb is None:
            failed += 1
            print(f"   ✗ falhou: {ev['slug']} (segue só com aresta lexical)")
            continue
        supabase.table("events").update({"embedding": emb}).eq("id", ev["id"]).execute()
        ev["embedding"] = emb
        fixed += 1
        print(f"   ✓ {ev['slug']}")
    return fixed, failed


# ── Union-find ────────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def parse_ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def build_clusters(
    events: list[dict],
    threshold: float,
    max_window_hours: float,
    category_guard: bool,
) -> list[list[int]]:
    """Retorna clusters (listas de índices em `events`) com 2+ membros."""
    n = len(events)
    uf = UnionFind(n)
    window = max_window_hours * 3600

    ts = np.array([parse_ts(e["occurred_at"]) for e in events])
    cats = [e.get("category") for e in events]
    hnorms = [normalize_headline(e.get("headline")) for e in events]

    # ── Arestas semânticas ──
    vecs = [parse_vector(e.get("embedding")) for e in events]
    have = [i for i, v in enumerate(vecs) if v is not None]
    if have:
        E = np.array([vecs[i] for i in have], dtype=np.float32)
        norms = np.linalg.norm(E, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        E = E / norms
        S = E @ E.T
        rows, cols = np.where(np.triu(S, k=1) >= threshold)
        for r, c in zip(rows.tolist(), cols.tolist()):
            i, j = have[r], have[c]
            sim = float(S[r, c])
            if abs(ts[i] - ts[j]) > window:
                continue
            if category_guard and sim < THRESH_UNCONDITIONAL and cats[i] != cats[j]:
                continue
            uf.union(i, j)

    # ── Arestas lexicais (headline normalizada idêntica) ──
    by_headline: dict[str, list[int]] = defaultdict(list)
    for i, h in enumerate(hnorms):
        if h:
            by_headline[h].append(i)
    for idxs in by_headline.values():
        for a in range(1, len(idxs)):
            i, j = idxs[0], idxs[a]
            if abs(ts[i] - ts[j]) <= window:
                uf.union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)
    return [g for g in groups.values() if len(g) > 1]


def pick_canonical(events: list[dict], cluster: list[int]) -> int:
    """Menor source_tier → occurred_at mais antigo → maior view_count → menor created_at."""
    return min(
        cluster,
        key=lambda i: (
            events[i].get("source_tier") or 2,
            parse_ts(events[i].get("occurred_at")),
            -(events[i].get("view_count") or 0),
            parse_ts(events[i].get("created_at")),
        ),
    )


# ── Similaridade individual p/ relatório ─────────────────────────────────────

def pair_sim(a: dict, b: dict) -> float | None:
    va, vb = parse_vector(a.get("embedding")), parse_vector(b.get("embedding"))
    if va is None or vb is None:
        return None
    x = np.asarray(va, dtype=np.float32)
    y = np.asarray(vb, dtype=np.float32)
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(np.dot(x, y) / denom) if denom else None


# ── Agregação de fontes ───────────────────────────────────────────────────────

def merge_secondary_sources(canonical: dict, dups: list[dict]) -> list:
    """
    Une secondary_sources do canônico + fontes (source_url e
    secondary_sources) dos duplicados. Dedup por URL; exclui a source_url
    do próprio canônico. Tolera entradas string (URLs) e dict {url,name,tier}.
    """
    def entry_url(entry) -> str | None:
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            return entry.get("url")
        return None

    merged: list = list(canonical.get("secondary_sources") or [])
    seen = {entry_url(e) for e in merged}
    seen.add(canonical.get("source_url"))
    seen.discard(None)

    for d in dups:
        candidates = [
            {"url": d.get("source_url"), "name": d.get("source_name", ""), "tier": d.get("source_tier", 2)}
        ]
        candidates.extend(d.get("secondary_sources") or [])
        for c in candidates:
            url = entry_url(c)
            if url and url not in seen:
                merged.append(c)
                seen.add(url)
    return merged


# ── Aplicação ────────────────────────────────────────────────────────────────

def apply_cluster(supabase: Client, canonical: dict, dups: list[dict]) -> bool:
    """Soft-merge de um cluster. Retorna False se o canônico não estiver mais ativo."""
    check = (
        supabase.table("events")
        .select("merged_into_id")
        .eq("id", canonical["id"])
        .single()
        .execute()
    ).data
    if check.get("merged_into_id") is not None:
        print(f"   ⚠️  canônico {canonical['slug']} já foi mesclado — cluster pulado")
        return False

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("events").update(
        {"secondary_sources": merge_secondary_sources(canonical, dups), "updated_at": now}
    ).eq("id", canonical["id"]).execute()

    dup_ids = [d["id"] for d in dups]
    supabase.table("events").update(
        {"merged_into_id": canonical["id"], "updated_at": now}
    ).in_("id", dup_ids).execute()
    return True


def trigger_revalidation() -> None:
    site = os.getenv("NEXT_PUBLIC_SITE_URL")
    secret = os.getenv("REVALIDATE_SECRET")
    if not site or not secret:
        print("⚠️  NEXT_PUBLIC_SITE_URL/REVALIDATE_SECRET ausentes — revalidação pulada")
        return
    try:
        resp = httpx.post(
            f"{site}/api/revalidate",
            json={"tags": ["events-feed"]},
            headers={"Authorization": f"Bearer {secret}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            print("✅ Cache do site revalidado")
        else:
            print(f"⚠️  Revalidação retornou {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"⚠️  Falha ao revalidar cache: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Trump Tracker — Limpeza de eventos duplicados")
    parser.add_argument("--apply", action="store_true", help="Executa os merges (default: dry-run)")
    parser.add_argument("--revalidate", action="store_true", help="Revalida o cache do site após aplicar")
    parser.add_argument("--threshold", type=float, default=0.80, help="Similaridade mínima (default 0.80)")
    parser.add_argument("--max-window-hours", type=float, default=72.0, help="Janela temporal máxima entre duplicatas (default 72h)")
    parser.add_argument("--no-category-guard", action="store_true", help="Não exigir mesma categoria na faixa 0.80–0.91")
    args = parser.parse_args()

    for var in ("SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY"):
        if not os.getenv(var):
            print(f"❌ Variável de ambiente faltando: {var}")
            sys.exit(1)

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("📥 Baixando events ativos...")
    events = fetch_active_events(supabase)
    print(f"   {len(events)} eventos ativos")

    fixed, failed = backfill_embeddings(supabase, openai_client, events)
    if fixed or failed:
        print(f"   Backfill: {fixed} corrigido(s), {failed} falha(s)")

    print(
        f"🔍 Clusterizando (threshold={args.threshold}, janela={args.max_window_hours:.0f}h, "
        f"guard de categoria={'off' if args.no_category_guard else 'on'})..."
    )
    clusters = build_clusters(
        events,
        threshold=args.threshold,
        max_window_hours=args.max_window_hours,
        category_guard=not args.no_category_guard,
    )

    if not clusters:
        print("✅ Nenhuma duplicata encontrada.")
        return

    clusters.sort(key=lambda c: -len(c))
    total_dups = sum(len(c) - 1 for c in clusters)

    print(f"\n{'═' * 70}")
    print(f"  {len(clusters)} cluster(s) · {total_dups} evento(s) a mesclar")
    print(f"  {len(events)} ativos → {len(events) - total_dups} após merge")
    print(f"{'═' * 70}")

    plan: list[tuple[dict, list[dict]]] = []
    for ci, cluster in enumerate(clusters, 1):
        canon_idx = pick_canonical(events, cluster)
        canon = events[canon_idx]
        dups = [events[i] for i in cluster if i != canon_idx]
        plan.append((canon, dups))

        span_days = (
            max(parse_ts(events[i]["occurred_at"]) for i in cluster)
            - min(parse_ts(events[i]["occurred_at"]) for i in cluster)
        ) / 86400
        warn = f"  ⚠️ span {span_days:.1f}d" if span_days > CLUSTER_SPAN_WARN_DAYS else ""

        print(f"\n— Cluster {ci} ({len(cluster)} eventos){warn}")
        print(f"  ✦ CANÔNICO  [{canon.get('category')}] tier {canon.get('source_tier')} · {canon['occurred_at'][:10]}")
        print(f"    {canon['headline'][:80]}")
        print(f"    /event/{canon['slug']}")
        for d in dups:
            sim = pair_sim(canon, d)
            sim_txt = f"sim={sim:.3f}" if sim is not None else "lexical"
            print(f"  ✗ mesclar   [{d.get('category')}] tier {d.get('source_tier')} · {d['occurred_at'][:10]} · {sim_txt}")
            print(f"    {d['headline'][:80]}")
            print(f"    /event/{d['slug']}")

    if not args.apply:
        print(f"\n{'═' * 70}")
        print("  DRY-RUN — nada foi alterado. Use --apply para executar os merges.")
        print(f"{'═' * 70}\n")
        return

    print(f"\n🚀 Aplicando {len(plan)} merge(s)...")
    applied = skipped = 0
    for canon, dups in plan:
        if apply_cluster(supabase, canon, dups):
            applied += 1
        else:
            skipped += 1

    print(f"\n✅ {applied} cluster(s) mesclado(s), {skipped} pulado(s)")
    print(f"   Eventos removidos do feed: {sum(len(d) for _, d in plan)}")

    if args.revalidate:
        trigger_revalidation()


if __name__ == "__main__":
    main()
