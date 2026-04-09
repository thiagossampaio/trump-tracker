"""
classify_agent.py
-----------------
Lê artigos raw_articles com status='pending', classifica via Claude Sonnet
com Prompt Caching, e roteia por score para os próximos agentes do pipeline.

Fluxo:
  1. Busca artigos pending (prioridade primeiro, depois mais recentes)
  2. Divide em batches de 5 para o Claude
  3. Claude retorna JSON com score, categoria, headline/summary em pt-BR
  4. Roteia por score: ≤3 → rejected, 4–7 → classified, ≥8 → classified + needs_human_review
  5. Atualiza tabela raw_articles com todos os campos de classificação
  6. Imprime relatório

Uso:
  python agents/classify_agent.py
  python agents/classify_agent.py --batch-size 50
  python agents/classify_agent.py --dry-run
  python agents/classify_agent.py --dry-run --limit 5
  python agents/classify_agent.py --limit 100
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("classify")

# ── Constantes ────────────────────────────────────────────────────────────────

BODY_TRUNCATE = 800
CLAUDE_INNER_BATCH = 5
MODEL = "claude-sonnet-4-6"

VALID_CATEGORIES = {
    "Institucional", "Econômico", "Diplomático",
    "Jurídico", "Militar", "Social", "Comunicação",
}
VALID_CONFIDENCE = {"high", "medium", "low"}

REQUIRED_ENV = ["SUPABASE_URL", "SUPABASE_KEY", "ANTHROPIC_API_KEY"]

# ── System Prompt (estável — alvo de Prompt Caching) ─────────────────────────

SYSTEM_PROMPT = """Você é um historiador e cientista político especializado na história da presidência americana.
Sua tarefa é avaliar artigos de notícias sobre Donald Trump e pontuar o quão historicamente aberrante cada evento é, comparado às normas da presidência americana.

## Aberration Score (1–10)

O score é a SOMA de 4 dimensões:

### A. Precedente histórico (0–4)
- 0: Aconteceu antes, múltiplas vezes, nos últimos 50 anos
- 1: Aconteceu antes, mas há mais de 50 anos
- 2: Aconteceu uma vez, em circunstâncias muito diferentes
- 3: Sem precedente direto, análogos parciais existem
- 4: Absolutamente sem precedente na história da república americana

### B. Velocidade / escalada (0–2)
- 0: Decisão gradual com sinalizações anteriores
- 1: Decisão abrupta sem aviso
- 2: Reverteu ou escalou em 48h de declaração anterior do próprio Trump

### C. Impacto institucional (0–2)
- 0: Impacto apenas na política pública (reversível)
- 1: Impacto em normas não-escritas (erosão de precedente)
- 2: Impacto em estruturas constitucionais ou legais

### D. Reação do sistema (0–2)
- 0: Reação normal de oposição partidária
- 1: Reação bipartidária ou de instituições neutras
- 2: Reação de aliados, militares, judiciário federal ou mercados

### Tabela de referência

| Score | Classificação             |
|-------|---------------------------|
| 1–3   | Normal presidencial       |
| 4–5   | Incomum                   |
| 6–7   | Raro                      |
| 8–9   | Sem precedente recente    |
| 10    | Sem precedente histórico  |

## Categorias (use exatamente como escrito)

- Institucional — ataques a checks and balances, demissões de independentes
- Econômico — tarifas, política comercial, sanções, mercados
- Diplomático — relações internacionais, OTAN, alianças, tratados
- Jurídico — processos, indultos, obstrução, privilégios executivos
- Militar — forças armadas, estado de emergência, cadeia de comando
- Social — direitos civis, imigração, minorias, saúde pública
- Comunicação — declarações falsas documentadas, ataques à imprensa

## Padrão de headline (pt-BR)

- Máximo 15 palavras
- Tempo verbal: passado simples
- Sem adjetivos avaliativos
- Incluir contraste quando existir
- Exemplo: "Trump demite diretor do FBI dois dias após negar que o faria"

## Padrão de summary (pt-BR)

3 frases máximo:
1. O que aconteceu (fato)
2. Por que é incomum (contexto histórico)
3. Reação imediata se relevante

## Formato de saída

Responda com um JSON array puro. Sem markdown. Sem explicações. Sem preâmbulo.
Cada elemento deve ter exatamente estas chaves:

{
  "article_id": "<uuid do input>",
  "is_aberrant": <true|false>,
  "score": <inteiro 1-10>,
  "score_breakdown": {
    "precedent": <0-4>,
    "velocity": <0-2>,
    "inst_impact": <0-2>,
    "system_reaction": <0-2>
  },
  "category": "<uma das 7 categorias acima, ortografia exata em português>",
  "headline_pt": "<headline em pt-BR, máx 15 palavras>",
  "summary_pt": "<summary em pt-BR, máx 3 frases>",
  "historical_context": "<2-3 frases de contexto histórico em pt-BR>",
  "confidence": "<high|medium|low>",
  "needs_human_review": <true|false>
}

Regras obrigatórias:
- O array deve ter exatamente tantos elementos quantos artigos no input.
- A ordem deve seguir a ordem do input.
- Se o artigo não for sobre Trump ou tiver conteúdo insuficiente, defina is_aberrant=false e score=1.
- score deve ser igual à soma de precedent + velocity + inst_impact + system_reaction.
- needs_human_review deve ser true se score >= 8 OU confidence = "low"."""


# ── Dataclass de relatório ────────────────────────────────────────────────────

@dataclass
class ClassifyReport:
    total_fetched: int = 0
    batches_sent: int = 0
    classified: int = 0
    rejected: int = 0
    needs_review: int = 0
    json_errors: int = 0
    errors: list[str] = field(default_factory=list)

    def print(self):
        print("\n" + "─" * 55)
        print("✅  Classificação concluída")
        print("─" * 55)
        print(f"   Artigos buscados:              {self.total_fetched:>4}")
        print(f"   Batches enviados ao Claude:    {self.batches_sent:>4}")
        print(f"   Classificados:                 {self.classified:>4}")
        print(f"   Rejeitados (score ≤ 3):        {self.rejected:>4}")
        print(f"   Para revisão humana:           {self.needs_review:>4}")
        if self.json_errors:
            print(f"   Erros de JSON (batch pulado): {self.json_errors:>4}")
        if self.errors:
            print(f"\n   ⚠️  Erros ({len(self.errors)}):")
            for e in self.errors:
                print(f"      • {e}")
        print(f"\n   Próximo passo: dedup_agent.py")
        print("─" * 55 + "\n")


# ── Helpers de ambiente e banco ───────────────────────────────────────────────

def check_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        log.error(f"Variáveis de ambiente faltando: {', '.join(missing)}")
        sys.exit(1)


def fetch_pending_articles(supabase: Client, limit: int) -> list[dict]:
    try:
        result = (
            supabase.table("raw_articles")
            .select("id, title, body, source_name, source_tier, published_at, priority")
            .eq("status", "pending")
            .order("priority", desc=True)
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        log.error(f"Erro ao buscar artigos pending: {e}")
        return []


# ── Construção dos prompts ────────────────────────────────────────────────────

def build_classification_prompt(articles: list[dict]) -> str:
    items = []
    for a in articles:
        body = (a.get("body") or "")[:BODY_TRUNCATE]
        items.append({
            "article_id": a["id"],
            "title": a.get("title", ""),
            "source": f"{a.get('source_name', '')} (tier {a.get('source_tier', '?')})",
            "published_at": a.get("published_at", ""),
            "body": body,
        })
    return (
        f"Classifique os seguintes {len(articles)} artigos. "
        f"Retorne um JSON array com {len(articles)} objetos.\n\n"
        + json.dumps(items, ensure_ascii=False, indent=2)
    )


# ── Chamada à API Anthropic ───────────────────────────────────────────────────

def classify_batch(client: anthropic.Anthropic, articles: list[dict]) -> list[dict] | None:
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": build_classification_prompt(articles),
            }],
        )
        raw_text = response.content[0].text

        # Log cache usage se disponível
        usage = getattr(response, "usage", None)
        if usage:
            created = getattr(usage, "cache_creation_input_tokens", 0)
            read = getattr(usage, "cache_read_input_tokens", 0)
            if created:
                log.info(f"Claude: cache criado ({created} tokens)")
            elif read:
                log.info(f"Claude: cache hit ({read} tokens lidos)")

        return parse_claude_response(raw_text)

    except anthropic.RateLimitError:
        log.warning("Claude: rate limit atingido. Batch pulado — tente novamente em alguns segundos.")
        return None
    except Exception as e:
        log.warning(f"Claude: erro na chamada — {e}")
        return None


def parse_claude_response(raw_text: str) -> list[dict] | None:
    # Strip markdown fences se presentes
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        log.warning("Claude: resposta JSON não é um array")
        return None
    except Exception as e:
        log.warning(f"Claude: JSON inválido — {e}\nTexto recebido: {raw_text[:200]}")
        return None


# ── Validação e roteamento ────────────────────────────────────────────────────

def validate_article_result(result: dict) -> bool:
    required_keys = {
        "article_id", "is_aberrant", "score", "score_breakdown",
        "category", "headline_pt", "summary_pt", "historical_context",
        "confidence", "needs_human_review",
    }
    if not required_keys.issubset(result.keys()):
        missing = required_keys - result.keys()
        log.warning(f"Resultado faltando chaves: {missing}")
        return False

    score = result.get("score")
    if not isinstance(score, int) or not (1 <= score <= 10):
        log.warning(f"Score inválido: {score!r}")
        return False

    bd = result.get("score_breakdown", {})
    breakdown_rules = {
        "precedent": (0, 4),
        "velocity": (0, 2),
        "inst_impact": (0, 2),
        "system_reaction": (0, 2),
    }
    for key, (lo, hi) in breakdown_rules.items():
        val = bd.get(key)
        if not isinstance(val, int) or not (lo <= val <= hi):
            log.warning(f"score_breakdown.{key} inválido: {val!r}")
            return False

    expected_sum = sum(bd[k] for k in breakdown_rules)
    if expected_sum != score:
        log.warning(
            f"score={score} != soma breakdown={expected_sum} — aceitando score do Claude"
        )

    if result.get("category") not in VALID_CATEGORIES:
        log.warning(f"Categoria inválida: {result.get('category')!r}")
        return False

    if result.get("confidence") not in VALID_CONFIDENCE:
        log.warning(f"Confidence inválida: {result.get('confidence')!r}")
        return False

    return True


def route_by_score(result: dict) -> tuple[str, bool]:
    score = result["score"]
    confidence = result.get("confidence", "high")

    if score <= 3:
        return "rejected", False
    elif score <= 7:
        needs_review = confidence == "low"
        return "classified", needs_review
    else:  # >= 8
        return "classified", True


def build_update_payload(result: dict, new_status: str, needs_review: bool) -> dict:
    return {
        "status": new_status,
        "headline_pt": result.get("headline_pt"),
        "summary_pt": result.get("summary_pt"),
        "historical_context": result.get("historical_context"),
        "score": result["score"],
        "score_breakdown": result.get("score_breakdown"),
        "category": result.get("category"),
        "confidence": result.get("confidence"),
        "needs_human_review": needs_review,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Atualização no banco ──────────────────────────────────────────────────────

def update_article(
    supabase: Client,
    article_id: str,
    payload: dict,
    dry_run: bool,
):
    status = payload["status"]
    score = payload["score"]
    category = payload.get("category", "?")
    needs_review = payload.get("needs_human_review", False)

    if dry_run:
        log.info(
            f"[DRY RUN] Would update {article_id}: "
            f"status={status}, score={score}, category={category}, "
            f"needs_human_review={needs_review}"
        )
        return

    try:
        supabase.table("raw_articles").update(payload).eq("id", article_id).execute()
    except Exception as e:
        log.error(f"Erro ao atualizar artigo {article_id}: {e}")
        raise


# ── Orquestração de batch ─────────────────────────────────────────────────────

def process_batch(
    supabase: Client,
    client: anthropic.Anthropic,
    articles: list[dict],
    report: ClassifyReport,
    dry_run: bool,
):
    ids = [a["id"] for a in articles]
    log.info(f"Classificando batch de {len(articles)} artigos via Claude...")

    results = classify_batch(client, articles)
    if results is None:
        report.json_errors += 1
        log.warning(f"Batch pulado — {len(articles)} artigos permanecem pending")
        return

    article_map = {a["id"]: a for a in articles}

    for res in results:
        aid = res.get("article_id")
        if aid not in article_map:
            log.warning(f"article_id desconhecido na resposta do Claude: {aid!r}")
            continue

        if not validate_article_result(res):
            log.warning(f"Resultado inválido para {aid} — artigo permanece pending")
            report.errors.append(f"Validação falhou para {aid}")
            continue

        new_status, needs_review = route_by_score(res)
        payload = build_update_payload(res, new_status, needs_review)

        try:
            update_article(supabase, aid, payload, dry_run)
        except Exception as e:
            report.errors.append(f"Erro ao atualizar {aid}: {e}")
            continue

        if new_status == "rejected":
            report.rejected += 1
        else:
            report.classified += 1
        if needs_review:
            report.needs_review += 1

    # Artigos do input que não voltaram na resposta permanecem pending
    returned_ids = {r.get("article_id") for r in results}
    missing = set(ids) - returned_ids
    if missing:
        log.warning(f"Claude não retornou resultado para {len(missing)} artigo(s) — permanecem pending")


def chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


# ── Entry point assíncrono ────────────────────────────────────────────────────

async def run(
    batch_size: int = 50,
    dry_run: bool = False,
    limit: int | None = None,
) -> ClassifyReport:
    check_env()

    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    fetch_limit = limit if limit is not None else batch_size
    articles = fetch_pending_articles(supabase, fetch_limit)
    report = ClassifyReport(total_fetched=len(articles))

    if not articles:
        log.info("Nenhum artigo pending encontrado.")
        report.print()
        return report

    log.info(f"Encontrados {len(articles)} artigos pending — processando em batches de {CLAUDE_INNER_BATCH}")

    for inner_batch in chunks(articles, CLAUDE_INNER_BATCH):
        report.batches_sent += 1
        process_batch(supabase, client, inner_batch, report, dry_run)

    report.print()
    return report


def main():
    parser = argparse.ArgumentParser(description="Trump Tracker — Classify Agent")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Número de artigos a buscar do banco por execução (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa sem gravar no banco",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite máximo de artigos a processar",
    )
    args = parser.parse_args()
    asyncio.run(run(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        limit=args.limit,
    ))


if __name__ == "__main__":
    main()
