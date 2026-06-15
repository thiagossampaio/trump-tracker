"""
send_review_batch.py
---------------------
Reenvia um lote CURADO de artigos em pending_review para o Telegram, após
o conserto do webhook (os cards antigos nunca foram acionáveis).

Passos:
  1. Dedup lexical de TODA a fila pending_review: para cada grupo de
     headlines normalizadas idênticas, mantém um canônico (melhor tier,
     mais recente) e marca os demais como rejected + duplicate_of_article_id
     (o publish fecha a linhagem quando o canônico for publicado).
  2. Dos sobreviventes, filtra score >= --min-score, ordena por mais
     recente e envia até --limit cards (com pausa anti-flood).

Os cards enviados JÁ estão em pending_review — o callback_data é o id do
artigo, que continua válido com o webhook corrigido.

Uso (do ambiente local, .env na raiz):
  python scripts/send_review_batch.py --dry-run
  python scripts/send_review_batch.py
  python scripts/send_review_batch.py --min-score 9 --limit 10
  python scripts/send_review_batch.py --no-dedup
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "agents"))
from embedding_utils import normalize_headline  # noqa: E402
from telegram_agent import build_card, build_keyboard  # noqa: E402

load_dotenv(os.path.join(REPO_ROOT, ".env"))

PAGE_SIZE = 1000
SEND_DELAY_S = 0.6  # ~1.6 msg/s — abaixo do limite do Telegram p/ um chat


def parse_ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def fetch_all_pending(supabase: Client) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = (
            supabase.table("raw_articles")
            .select(
                "id, headline_pt, summary_pt, score, score_breakdown, "
                "source_name, source_tier, url, category, published_at"
            )
            .eq("status", "pending_review")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        ).data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def dedup_lexical(supabase: Client, rows: list[dict], dry_run: bool) -> set[str]:
    """Colapsa headlines idênticas. Retorna o conjunto de ids rejeitados."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        h = normalize_headline(r.get("headline_pt"))
        if h:
            groups[h].append(r)

    rejected: set[str] = set()
    for h, members in groups.items():
        if len(members) < 2:
            continue
        # canônico: melhor tier (menor), depois mais recente
        canonical = min(
            members,
            key=lambda m: (m.get("source_tier") or 2, -parse_ts(m.get("published_at"))),
        )
        for m in members:
            if m["id"] == canonical["id"]:
                continue
            rejected.add(m["id"])
            if not dry_run:
                supabase.table("raw_articles").update(
                    {"status": "rejected", "duplicate_of_article_id": canonical["id"]}
                ).eq("id", m["id"]).execute()

    print(
        f"   Dedup lexical: {len(rejected)} cópia(s) redundante(s) "
        f"{'seriam marcadas' if dry_run else 'marcadas'} como rejected"
    )
    return rejected


def send_card(client: httpx.Client, article: dict, token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": build_card(article),
        "reply_markup": json.dumps(build_keyboard(article["id"])),
    }
    try:
        resp = client.post(url, json=payload, timeout=15.0)
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            return True
        if resp.status_code == 429:
            retry = data.get("parameters", {}).get("retry_after", 5)
            print(f"   429 — aguardando {retry}s")
            time.sleep(retry + 1)
            return send_card(client, article, token, chat_id)
        print(f"   ✗ {article['id']}: {data}")
        return False
    except Exception as e:
        print(f"   ✗ {article['id']}: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="Reenvio curado de pending_review ao Telegram")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-dedup", action="store_true", help="Não colapsar headlines idênticas")
    ap.add_argument("--min-score", type=int, default=8)
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    for v in ("SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if not os.getenv(v):
            print(f"❌ Falta variável: {v}")
            sys.exit(1)

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    print("📥 Carregando pending_review...")
    rows = fetch_all_pending(supabase)
    print(f"   {len(rows)} artigos em pending_review")

    rejected: set[str] = set()
    if not args.no_dedup:
        rejected = dedup_lexical(supabase, rows, args.dry_run)

    survivors = [r for r in rows if r["id"] not in rejected]
    eligible = [r for r in survivors if (r.get("score") or 0) >= args.min_score]
    eligible.sort(key=lambda r: parse_ts(r.get("published_at")), reverse=True)
    batch = eligible[: args.limit]

    print(
        f"\n🎯 Lote: score ≥ {args.min_score}, {len(eligible)} elegíveis "
        f"→ enviando {len(batch)} (mais recentes)"
    )
    for r in batch:
        print(f"   · s{r.get('score')} · {r.get('published_at', '')[:10]} · "
              f"{(r.get('headline_pt') or '')[:62]}")

    if args.dry_run:
        print("\n   DRY-RUN — nada enviado, nenhuma dedup aplicada.\n")
        return

    print(f"\n📤 Enviando {len(batch)} cards ao Telegram...")
    sent = 0
    with httpx.Client() as client:
        for r in batch:
            if send_card(client, r, token, chat_id):
                sent += 1
            time.sleep(SEND_DELAY_S)

    print(f"\n✅ {sent}/{len(batch)} cards enviados. Clique em Publicar/Rejeitar.")


if __name__ == "__main__":
    main()
