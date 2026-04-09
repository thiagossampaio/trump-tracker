# Trump Tracker — Especificações Estruturadas

> **Versão:** 1.0.0
> **Data:** 2026-04-08
> **Baseado em:** `artifacts/20260408_initial/briefings/v0.md`
> **Status:** Aprovado para implementação

---

## Índice

- [SPEC-01 — Agente de Classificação IA](#spec-01--agente-de-classificação-ia)
- [SPEC-02 — Agente de Deduplicação Semântica](#spec-02--agente-de-deduplicação-semântica)
- [SPEC-03 — Moderação via Telegram](#spec-03--moderação-via-telegram)
- [SPEC-04 — Agente de Publicação](#spec-04--agente-de-publicação)
- [SPEC-05 — Orquestração CI/CD](#spec-05--orquestração-cicd)
- [SPEC-06 — Frontend Público](#spec-06--frontend-público)
- [SPEC-07 — Backfill Histórico](#spec-07--backfill-histórico)

---

## SPEC-01 — Agente de Classificação IA

**Objetivo**
> Implementar `agents/classify_agent.py`, que lê artigos com `status='pending'` do Supabase, chama o Claude Sonnet em batches de 5 para avaliar aberração histórica, e atualiza o status e metadados de cada artigo no banco.

**Contexto**
> O `ingest_agent.py` já persiste artigos em `raw_articles` com `status='pending'`. O classify_agent é o segundo passo do pipeline, responsável por eliminar eventos rotineiros (score ≤ 3), rotear eventos moderados (4–7) para deduplicação, e escalar eventos críticos (≥ 8) para revisão humana via Telegram. Sem este agent, nenhum evento chega ao feed público.

**Comportamento esperado**

1. Conecta ao Supabase usando `SUPABASE_URL` e `SUPABASE_KEY`.
2. Busca até 50 artigos com `status='pending'`, ordenados por `priority DESC, published_at DESC`.
3. Para cada batch de 5 artigos:
   a. Trunca o corpo de cada artigo para 800 caracteres.
   b. Constrói um único prompt com todos os 5 artigos no formato JSON array.
   c. Chama `claude-sonnet-4-20250514` com Prompt Caching ativado no system prompt.
   d. Recebe resposta JSON (sem markdown) com um objeto por artigo.
4. Para cada artigo classificado:
   - Se `is_aberrant = false` ou `score ≤ 3` → `UPDATE status='rejected'`
   - Se `score` entre 4 e 7 → `UPDATE status='classified'` (segue para dedup)
   - Se `score ≥ 8` → `UPDATE status='classified'`, enfileira para `telegram_agent`
   - Se `confidence='low'` → independente do score, enfileira para revisão humana
5. Registra `processed_at = NOW()` em todos os artigos processados.
6. Imprime relatório: total processados, rejeitados, classificados, enviados para Telegram.
7. Aceita `--dry-run` (sem escrita no banco) e `--limit N` (máximo de artigos a processar).

**Campos esperados na resposta do Claude (por artigo):**

```json
{
  "article_id": "uuid",
  "is_aberrant": true,
  "score": 7,
  "score_breakdown": {
    "precedent": 3,
    "velocity": 2,
    "inst_impact": 1,
    "system_reaction": 1
  },
  "category": "Institucional",
  "headline_pt": "Trump demite diretor do FBI dois dias após negar que o faria",
  "summary_pt": "Frase 1. Frase 2. Frase 3.",
  "historical_context": "Contexto histórico em 2–3 frases.",
  "confidence": "high",
  "needs_human_review": false
}
```

**Regras de negócio**

- DEVE processar artigos em batches de exatamente 5 (ou menos no último batch).
- DEVE usar `anthropic.beta.prompt_caching` no system prompt para reduzir custo em runs consecutivos.
- DEVE truncar corpo para 800 caracteres antes de enviar ao Claude.
- DEVE registrar `processed_at` em todos os artigos processados, inclusive rejeitados.
- NÃO DEVE publicar nem modificar a tabela `events` — escopo exclusivo de `raw_articles`.
- SE `confidence='low'` ENTÃO `needs_human_review=true` independente do score.
- SE score ≥ 8 OU `needs_human_review=true` ENTÃO o agent notifica o `telegram_agent` (via UPDATE de um campo auxiliar ou chamada direta no mesmo run).
- DEVE ser idempotente: artigos com `status != 'pending'` são ignorados.
- NÃO DEVE falhar o pipeline se o Claude retornar JSON inválido para um batch — logar erro, marcar artigos do batch com `status='pending'` novamente, e continuar.
- O sistema de categorias canônicas DEVE ser respeitado: Institucional, Econômico, Diplomático, Jurídico, Militar, Social, Comunicação.
- Headlines DEVEM seguir o padrão: máximo 15 palavras, tempo verbal passado simples, sem adjetivos avaliativos.
- Summaries DEVEM ter máximo 3 frases: fato, contexto histórico, reação imediata.

**Critérios de aceite**

- DADO artigos `pending` no banco QUANDO o agent executa ENTÃO todos são processados e nenhum permanece `pending` após a execução (exceto erros de API).
- DADO artigo com score ≤ 3 QUANDO classificado ENTÃO `status='rejected'` e `processed_at` preenchido.
- DADO artigo com score entre 4 e 7 QUANDO classificado ENTÃO `status='classified'` com todos os campos preenchidos.
- DADO artigo com score ≥ 8 QUANDO classificado ENTÃO `status='classified'` e `needs_human_review=true`.
- DADO `confidence='low'` em qualquer score QUANDO classificado ENTÃO `needs_human_review=true`.
- DADO `--dry-run` QUANDO executado ENTÃO nenhuma escrita no banco, apenas log do que seria feito.
- DADO erro de JSON inválido do Claude QUANDO ocorre ENTÃO o batch é ignorado, artigos voltam para `pending`, pipeline não interrompe.
- DADO 5 artigos em batch QUANDO chamada ao Claude ENTÃO 1 única chamada de API (não 5).

**Estado atual**
> `agents/classify_agent.py` não existe. `.claude/skills/trump-tracker/classify.md` existe como documentação de comportamento esperado, mas não há código.

**Mudanças necessárias**

- **Banco de dados:** Pré-requisito — `supabase/schema.sql` deve ter o CHECK constraint atualizado (ver WP-00) para incluir `'approved'` e `'approved_manual'` antes de qualquer execução deste agent.
- **Backend:** Criar `agents/classify_agent.py` com as funções: `fetch_pending_articles()`, `build_classification_prompt()`, `classify_batch()`, `route_by_score()`, `update_articles()`, `main()`.
- **Requirements:** Descomentar `anthropic==0.28.0` em `requirements.txt` (ou versão mais recente compatível com Prompt Caching).
- **Configuração:** Nenhum novo arquivo de config necessário — usa `.env` existente.

**Definição de pronto**

- [ ] Funcionalidade implementada conforme comportamento esperado
- [ ] Todos os critérios de aceite validados
- [ ] `--dry-run` funciona sem nenhuma escrita no banco
- [ ] Batching de 5 artigos confirmado via log (1 chamada por batch)
- [ ] Prompt Caching ativo (verificar `cache_creation_input_tokens` na resposta da API)
- [ ] Tratamento de erro de JSON inválido testado manualmente
- [ ] Código revisado por outro membro do time
- [ ] Documentação `docs/pipeline/classify.mdx` criada

---

## SPEC-02 — Agente de Deduplicação Semântica

**Objetivo**
> Implementar `agents/dedup_agent.py`, que detecta eventos duplicados ou relacionados usando embeddings vetoriais (pgvector) e decide se um artigo classificado deve ser publicado como novo evento, mesclado a um existente, ou descartado.

**Contexto**
> Após a classificação, artigos com `status='classified'` e score entre 4 e 7 chegam ao dedup_agent. O mesmo episódio (ex: demissão de um funcionário) pode gerar dezenas de coberturas de fontes distintas. O dedup previne que o feed exiba múltiplos cards para o mesmo fato, usando similaridade semântica entre embeddings ao invés de dedup por URL (já feito no ingest).

**Comportamento esperado**

1. Busca artigos com `status='classified'` e `needs_human_review=false` na tabela `raw_articles`.
2. Para cada artigo:
   a. Gera embedding via `text-embedding-3-small` (OpenAI) do texto: `"{headline_pt} {summary_pt} {category}"`.
   b. Consulta a tabela `events` via pgvector: `SELECT id, slug, occurred_at, embedding <=> $1 AS similarity FROM events ORDER BY similarity LIMIT 5`.
   c. Aplica tabela de decisão por similaridade cosine:

| Similaridade | Ação |
|---|---|
| ≥ 0.92 | **Duplicata** — descartar (`status='rejected'`) |
| 0.80–0.91 | **Mesmo episódio** — avaliar se é update ou duplicata (ver regras) |
| 0.65–0.79 | **Relacionado** — publicar separado; preencher `secondary_sources` no evento existente |
| < 0.65 | **Independente** — publicar como novo evento |

3. Para artigos independentes ou relacionados: `UPDATE raw_articles SET status='approved'`.
4. Para duplicatas confirmadas: `UPDATE raw_articles SET status='rejected'`.
5. Para mesclagem (0.80–0.91 e critérios de update): `UPDATE raw_articles SET status='rejected', merged_into_id=<id do evento existente>` e enriquece o evento existente com a fonte adicional em `secondary_sources`.
6. Imprime relatório: total processados, novos, relacionados, mesclados, descartados.

**Lógica de update vs. duplicata (similaridade 0.80–0.91):**

- É UPDATE (publicar separado) SE:
  - `occurred_at` do novo artigo for > 2h após o evento existente, E
  - Título contiver termos de evolução: `blocks`, `responds`, `reverses`, `appeals`, `rules`, `overturns`
- É DUPLICATA (descartar) SE:
  - `occurred_at` estiver dentro de 4h do evento existente, OU
  - Não adicionar informação nova (ausência dos termos acima)

**Regras de negócio**

- DEVE processar apenas artigos com `status='classified'` e `needs_human_review=false`.
- DEVE gerar embedding com o texto composto: `"{headline_pt} {summary_pt} {category}"` (1536 dimensões).
- NUNCA DEVE deletar registros — apenas atualizar status.
- SE similaridade ≥ 0.92 ENTÃO descartar incondicionalmente.
- SE similaridade 0.80–0.91 ENTÃO aplicar lógica de update vs. duplicata.
- SE similaridade 0.65–0.79 ENTÃO publicar separado e adicionar URL da fonte ao `secondary_sources` do evento relacionado mais similar.
- SE similaridade < 0.65 ENTÃO publicar como novo evento independente.
- DEVE ser idempotente: re-processar o mesmo artigo produz o mesmo resultado.
- NÃO DEVE chamar o Claude — decisão é puramente vetorial.

**Critérios de aceite**

- DADO dois artigos sobre o mesmo evento (similaridade ≥ 0.92) QUANDO processados ENTÃO apenas um chega ao feed.
- DADO um artigo com similaridade 0.80–0.91 e occurred_at > 2h com termo "reverses" QUANDO processado ENTÃO `status='approved'` (novo evento).
- DADO um artigo com similaridade 0.80–0.91 e occurred_at < 4h QUANDO processado ENTÃO `status='rejected'` com `merged_into_id` preenchido.
- DADO artigo independente (similaridade < 0.65) QUANDO processado ENTÃO `status='approved'`.
- DADO `--dry-run` QUANDO executado ENTÃO nenhuma escrita, apenas log das decisões.
- DADO tabela `events` vazia QUANDO processado ENTÃO todos os artigos são marcados `approved` (sem comparação possível).

**Estado atual**
> `agents/dedup_agent.py` não existe. `.claude/skills/trump-tracker/dedup.md` existe como especificação de comportamento.

**Mudanças necessárias**

- **Backend:** Criar `agents/dedup_agent.py` com funções: `generate_embedding()`, `find_similar_events()`, `decide_action()`, `apply_decision()`, `main()`.
- **Requirements:** Descomentar `openai==1.30.0` em `requirements.txt`.
- **Banco de dados:** Índice `ivfflat` já existe em `events.embedding` — nenhuma mudança necessária.

**Definição de pronto**

- [ ] Funcionalidade implementada conforme comportamento esperado
- [ ] Todos os critérios de aceite validados
- [ ] Lógica de update vs. duplicata (faixa 0.80–0.91) testada com casos reais
- [ ] `--dry-run` funciona sem nenhuma escrita
- [ ] Nenhum registro deletado — apenas status atualizado
- [ ] Código revisado por outro membro do time
- [ ] Documentação `docs/pipeline/dedup.mdx` criada

---

## SPEC-03 — Moderação via Telegram

**Objetivo**
> Implementar `agents/telegram_agent.py` e `cloudflare/telegram-webhook.js` para enviar ao moderador, via Telegram Bot, cards de revisão de eventos com score ≥ 8, com botões inline para aprovar ou rejeitar — sem opção de edição.

**Contexto**
> Eventos com alto potencial de impacto (score ≥ 8) ou baixa confiança da IA não devem ser publicados automaticamente. O moderador recebe uma mensagem estruturada no Telegram e decide via toque. O Cloudflare Worker recebe o callback do Telegram e atualiza o Supabase. Zero infraestrutura em idle — o Worker acorda apenas quando o moderador responde.

**Comportamento esperado — `telegram_agent.py`**

1. Busca artigos com `status='classified'` e `needs_human_review=true` em `raw_articles`.
2. Para cada artigo, constrói e envia a seguinte mensagem ao `TELEGRAM_CHAT_ID`:

```
🔴 REVISÃO NECESSÁRIA — Score [N]/10

📰 [headline_pt]

📋 RESUMO:
[summary_pt]

📊 BREAKDOWN:
Precedente: [A]/4 · Velocidade: [B]/2
Institucional: [C]/2 · Reação: [D]/2

🔗 Fonte: [source_name]
[source_url]
```

3. Inclui inline keyboard com dois botões: `[✅ Publicar]` e `[❌ Rejeitar]`.
4. O `callback_data` de cada botão é `"publish:{article_id}"` ou `"reject:{article_id}"`.
5. Após envio bem-sucedido, `UPDATE raw_articles SET status='pending_review'` (aguardando resposta do moderador).
6. Aceita `--dry-run` (não envia mensagem, apenas loga o card).

**Nota:** Não há opção "Editar". Edições são feitas diretamente no Supabase caso necessário.

**Comportamento esperado — `cloudflare/telegram-webhook.js`**

1. Recebe POST do Telegram com `update.callback_query`.
2. Extrai `action` e `article_id` do `callback_data` (`"publish:uuid"` ou `"reject:uuid"`).
3. Se `action = 'publish'`:
   - `PATCH raw_articles SET status='approved_manual'` via Supabase REST API.
   - Responde ao Telegram: `answerCallbackQuery` com texto `"✅ Aprovado! Será publicado no próximo run."`.
4. Se `action = 'reject'`:
   - `PATCH raw_articles SET status='rejected'` via Supabase REST API.
   - Responde ao Telegram: `answerCallbackQuery` com texto `"❌ Rejeitado."`.
5. Responde `200 OK` ao Telegram em todos os casos (evitar retry do Telegram).
6. Rejeita métodos não-POST com `405 Method Not Allowed`.

**Setup do webhook:**

Após deploy do Worker, configurar uma única vez via API do Telegram:
```
POST https://api.telegram.org/bot{TOKEN}/setWebhook
Body: {"url": "https://{worker-name}.workers.dev"}
```

**Regras de negócio**

- DEVE enviar card apenas para artigos com `needs_human_review=true`.
- NÃO DEVE publicar evento automaticamente se `needs_human_review=true` — mesmo que o classify_agent atribua score 4–7 com `confidence='low'`.
- O inline keyboard DEVE ter exatamente dois botões: Publicar e Rejeitar. Sem botão de edição.
- O Worker DEVE responder ao Telegram em < 2 segundos (Telegram espera confirmação em até 2s).
- O Worker DEVE usar HTTPS para todas as chamadas ao Supabase.
- NUNCA DEVE armazenar o token do Telegram ou a chave do Supabase no código — apenas nas variáveis de ambiente do Worker (`wrangler secret put`).
- SE o moderador não responder, o artigo permanece em `status='pending_review'` indefinidamente — não há timeout automático na Fase 1.
- O `publish_agent` DEVE ignorar artigos com `status='pending_review'`.

**Status adicionais introduzidos por esta spec:**
- `pending_review` — enviado ao Telegram, aguardando resposta do moderador

> **Nota de schema:** O CHECK constraint de `raw_articles.status` DEVE incluir `'pending_review'`, `'approved_manual'`. Ver WP-00.

**Critérios de aceite**

- DADO artigo com `needs_human_review=true` QUANDO o agent executa ENTÃO card é enviado ao TELEGRAM_CHAT_ID em < 10 minutos.
- DADO card enviado QUANDO moderador clica `[✅ Publicar]` ENTÃO `status='approved_manual'` no banco.
- DADO card enviado QUANDO moderador clica `[❌ Rejeitar]` ENTÃO `status='rejected'` no banco.
- DADO `--dry-run` QUANDO executado ENTÃO nenhuma mensagem enviada ao Telegram.
- DADO request não-POST ao Worker ENTÃO resposta `405`.
- DADO `callback_data` inválido QUANDO recebido pelo Worker ENTÃO loga erro e responde `200` (não explode).
- DADO artigo com `status='pending_review'` QUANDO o `publish_agent` executa ENTÃO artigo é ignorado.

**Estado atual**
> `agents/telegram_agent.py` e `cloudflare/telegram-webhook.js` não existem. `.claude/skills/trump-tracker/review.md` existe. O briefing contém um esboço do webhook mas sem a lógica de edição (que foi removida desta spec).

**Mudanças necessárias**

- **Backend:** Criar `agents/telegram_agent.py`.
- **Cloudflare:** Criar `cloudflare/telegram-webhook.js`.
- **Banco de dados:** Adicionar `'pending_review'` ao CHECK constraint de `raw_articles.status` (WP-00).
- **Requirements:** Nenhuma lib adicional necessária — o `telegram_agent` usa `httpx` (já presente) para chamar a Bot API diretamente.
- **Cloudflare Worker:** Configurar variáveis de ambiente `SUPABASE_URL`, `SUPABASE_KEY`, `TELEGRAM_BOT_TOKEN` via `wrangler secret put`.

**Definição de pronto**

- [ ] Card formatado corretamente com todos os campos
- [ ] Inline keyboard com exatamente 2 botões (Publicar, Rejeitar)
- [ ] Aprovação via Telegram atualiza banco corretamente
- [ ] Rejeição via Telegram atualiza banco corretamente
- [ ] Worker responde em < 2s (verificado via Cloudflare Workers dashboard)
- [ ] Webhook configurado via `setWebhook` e testado com mensagem real
- [ ] Credenciais configuradas via `wrangler secret put` (não hardcoded)
- [ ] `--dry-run` testado
- [ ] Código revisado por outro membro do time
- [ ] Documentação `docs/pipeline/telegram.mdx` e `docs/infra/telegram-webhook.mdx` criadas

---

## SPEC-04 — Agente de Publicação

**Objetivo**
> Implementar `agents/publish_agent.py`, que pega artigos aprovados (auto ou via Telegram), gera embedding final, cria slug único, insere na tabela `events` e dispara revalidação do cache Next.js.

**Contexto**
> É o último passo do pipeline de backend. Após dedup (score 4–7, `status='approved'`) e moderação Telegram (score ≥ 8, `status='approved_manual'`), o publish_agent transforma artigos de `raw_articles` em eventos públicos na tabela `events`. Após cada publicação, sinaliza ao frontend Next.js para revalidar o cache ISR.

**Comportamento esperado**

1. Busca artigos com `status IN ('approved', 'approved_manual')` em `raw_articles`, ordenados por `published_at DESC`.
2. Para cada artigo:
   a. Gera embedding via `text-embedding-3-small` do texto: `"{headline_pt} {summary_pt} {category}"`.
   b. Gera slug no formato `{acao-kebab}-{YYYY-MM-DD}` usando o headline em português, normalizado com `unidecode` + lowercase + hifenização, truncado para 80 caracteres, com sufixo numérico em caso de colisão (`-2`, `-3`…).
   c. Monta dict do evento com todos os campos da tabela `events`.
   d. Executa `INSERT INTO events ... ON CONFLICT (slug) DO NOTHING`.
   e. `UPDATE raw_articles SET status='published'`.
3. Após todos os inserts, dispara `POST /api/revalidate` com `Authorization: Bearer {REVALIDATE_SECRET}` e body `{"tags": ["events-feed"]}`.
4. Imprime relatório: total publicados, conflitos ignorados, falhas.
5. Aceita `--dry-run`.

**Mapeamento `raw_articles` → `events`:**

| Campo `events` | Fonte |
|---|---|
| `headline` | `raw_articles.headline_pt` (campo gerado pelo classify_agent) |
| `summary` | `raw_articles.summary_pt` |
| `historical_context` | `raw_articles.historical_context` |
| `score` | `raw_articles.score` |
| `score_breakdown` | `raw_articles.score_breakdown` |
| `category` | `raw_articles.category` |
| `confidence` | `raw_articles.confidence` |
| `source_url` | `raw_articles.url` |
| `source_name` | `raw_articles.source_name` |
| `source_tier` | `raw_articles.source_tier` |
| `occurred_at` | `raw_articles.published_at` |
| `review_status` | `'auto'` se `status='approved'`; `'human_approved'` se `status='approved_manual'` |
| `raw_article_id` | `raw_articles.id` |
| `embedding` | gerado pelo publish_agent |

> **Nota:** Os campos `headline_pt`, `summary_pt`, `historical_context`, `score`, `score_breakdown`, `category`, `confidence`, `needs_human_review` precisam ser adicionados à tabela `raw_articles` como parte do WP-00 (schema fix), pois o `classify_agent` os gravará lá antes do publish_agent lê-los.

**Regras de negócio**

- DEVE processar apenas artigos com `status IN ('approved', 'approved_manual')`.
- SE `status='approved_manual'` ENTÃO `review_status='human_approved'` no evento.
- SE `status='approved'` ENTÃO `review_status='auto'` no evento.
- DEVE usar `ON CONFLICT (slug) DO NOTHING` para idempotência.
- NUNCA DEVE deletar eventos publicados — `merged_into_id` para mesclar.
- DEVE disparar revalidação do Next.js após cada batch de publicações (não por evento).
- SE a revalidação falhar ENTÃO logar warning mas não falhar o pipeline — o próximo run do cron revalidará.
- DEVE ser idempotente: re-executar não duplica eventos.

**Critérios de aceite**

- DADO artigo `approved` QUANDO publicado ENTÃO evento aparece na tabela `events` com todos os campos preenchidos.
- DADO artigo `approved_manual` QUANDO publicado ENTÃO `review_status='human_approved'` no evento.
- DADO dois artigos com o mesmo slug calculado QUANDO publicados ENTÃO segundo recebe sufixo `-2`.
- DADO revalidação falha de rede QUANDO ocorre ENTÃO pipeline não interrompe, warning logado.
- DADO `--dry-run` QUANDO executado ENTÃO nenhuma escrita no banco, nenhuma chamada de revalidação.
- DADO artigo já publicado (status='published') QUANDO o agent executa novamente ENTÃO ignorado (idempotência).

**Estado atual**
> `agents/publish_agent.py` não existe. `.claude/skills/trump-tracker/publish.md` existe.

**Mudanças necessárias**

- **Backend:** Criar `agents/publish_agent.py`.
- **Banco de dados (WP-00):** Adicionar colunas de classificação à tabela `raw_articles`: `headline_pt TEXT`, `summary_pt TEXT`, `historical_context TEXT`, `score SMALLINT`, `score_breakdown JSONB`, `category TEXT`, `confidence TEXT`, `needs_human_review BOOLEAN DEFAULT FALSE`.
- **Requirements:** `openai` e `unidecode` já estão no `requirements.txt`.

**Definição de pronto**

- [ ] Funcionalidade implementada conforme comportamento esperado
- [ ] Todos os critérios de aceite validados
- [ ] Slug gerado corretamente (kebab-case, sem acentos, sem colisão)
- [ ] Revalidação ISR disparada após publicação (verificar log do Next.js)
- [ ] `ON CONFLICT DO NOTHING` testado com slug duplicado
- [ ] `--dry-run` funcional
- [ ] Código revisado por outro membro do time
- [ ] Documentação `docs/pipeline/publish.mdx` criada

---

## SPEC-05 — Orquestração CI/CD

**Objetivo**
> Criar `.github/workflows/pipeline.yml` que executa o pipeline completo (ingest → classify → dedup → telegram → publish) de forma autônoma a cada 2 horas via GitHub Actions cron, com suporte a disparo manual com inputs opcionais.

**Contexto**
> Toda a lógica de automação vive no GitHub Actions. Não há servidor em idle — o pipeline acorda, executa os agents em sequência, e termina. O workflow é a cola que une os 4 agents Python, gerencia os secrets, e garante que o sistema opere sem intervenção humana.

**Comportamento esperado**

1. Disparo automático: `cron: '0 */2 * * *'` (a cada 2 horas, minuto 0).
2. Disparo manual (`workflow_dispatch`) com inputs opcionais:
   - `lookback_hours` (default: `4`) — janela de ingestão
   - `dry_run` (boolean, default: `false`) — executa sem gravar no banco
3. Sequência de execução:
   1. `python agents/ingest_agent.py --lookback-hours {lookback_hours} [--dry-run]`
   2. `python agents/classify_agent.py [--dry-run]`
   3. `python agents/dedup_agent.py [--dry-run]`
   4. `python agents/telegram_agent.py [--dry-run]`
   5. `python agents/publish_agent.py [--dry-run]`
4. Timeout do job: 20 minutos.
5. Runner: `ubuntu-latest`.
6. Python 3.12 com cache de pip.
7. Todos os secrets do GitHub mapeados para variáveis de ambiente do job.

**Secrets mapeados:**

```yaml
SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY,
NEWSAPI_KEY, GUARDIAN_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
REVALIDATE_SECRET, NEXT_PUBLIC_SITE_URL
```

**Regras de negócio**

- DEVE executar os agents em ordem sequencial (cada um depende do anterior).
- SE um agent falhar com exit code != 0 ENTÃO o workflow falha e os steps seguintes não executam.
- O `ingest_agent` DEVE receber `lookback_hours` do input do workflow (ou default 4).
- SE `dry_run=true` ENTÃO passar `--dry-run` para todos os agents.
- NUNCA DEVE commitar ou expor secrets nos logs.
- DEVE usar `actions/checkout@v4` e `actions/setup-python@v5`.
- O timeout de 20 minutos é suficiente para o pipeline completo em condições normais.

**Critérios de aceite**

- DADO cron às horas pares QUANDO dispara ENTÃO todos os 5 agents executam em sequência sem intervenção humana.
- DADO `workflow_dispatch` com `lookback_hours=48` QUANDO executado ENTÃO ingest usa janela de 48h.
- DADO `workflow_dispatch` com `dry_run=true` QUANDO executado ENTÃO nenhum dado é gravado no banco.
- DADO falha no `classify_agent` QUANDO ocorre ENTÃO `dedup_agent`, `telegram_agent` e `publish_agent` NÃO executam.
- DADO execução bem-sucedida QUANDO completa ENTÃO log do GitHub Actions mostra relatório de cada agent.

**Estado atual**
> `.github/workflows/pipeline.yml` não existe. O briefing contém o YAML completo como referência.

**Mudanças necessárias**

- **CI/CD:** Criar `.github/workflows/pipeline.yml`.
- **GitHub:** Configurar os 10 secrets no repositório (GitHub Settings → Secrets → Actions).
- **Configuração:** Nenhuma mudança em código de agents necessária — apenas o arquivo de workflow.

**Definição de pronto**

- [ ] Workflow criado e sintaxe YAML válida
- [ ] Cron disparou pelo menos uma vez com sucesso
- [ ] `workflow_dispatch` testado manualmente com `dry_run=true`
- [ ] Todos os secrets configurados no repositório GitHub
- [ ] Documentação `docs/infra/github-actions.mdx` criada

---

## SPEC-06 — Frontend Público

**Objetivo**
> Implementar `web/` com Next.js 15 App Router: feed público em scroll infinito com cards de eventos, página individual por slug, OG images dinâmicas, filtros por categoria, counter de aberrações, e deploy no Cloudflare Pages via `@opennextjs/cloudflare`.

**Contexto**
> O frontend é o produto final visível pelo usuário. Consome a tabela `events` do Supabase via API routes do próprio Next.js. Hospedado no Cloudflare Pages com ISR para servir o feed do CDN global. Otimizado para compartilhamento viral: cada evento tem URL canônica com OG image dinâmica.

**Comportamento esperado**

**Feed principal (`/`):**
1. Exibe cards de eventos em ordem cronológica reversa (mais recente primeiro).
2. Scroll infinito com cursor pagination (cursor = `occurred_at` do último evento carregado).
3. Tabs de filtro por categoria: Todos | Institucional | Econômico | Diplomático | Jurídico | Militar | Social | Comunicação.
4. Counter no header: "X aberrações desde a posse" (total de eventos no feed).
5. Carrega 20 eventos por página.

**Card de evento (`EventCard.tsx`):**
- Headline (máximo 2 linhas, trunca com ellipsis)
- `AberrationBadge` com score e cor semântica
- Emoji de categoria
- Data e nome da fonte (com link)
- Botão de compartilhamento nativo (Web Share API com fallback para clipboard)

**Página individual (`/event/[slug]`):**
1. Exibe todos os detalhes do evento: headline, summary completo, historical_context, score_breakdown visual, fonte(s), data.
2. Meta tags `og:title`, `og:description`, `og:image` (aponta para `/api/og?slug={slug}`).
3. Botão "← Voltar ao feed".
4. Link canônico absoluto.

**OG Image (`/api/og?slug={slug}`):**
- Gerada via `@vercel/og` (compatível com Cloudflare Workers via OpenNext).
- Layout: fundo preto, headline em branco (máx 2 linhas), badge de score em vermelho, categoria, logo/nome do site.
- Dimensões: 1200×630px (padrão Twitter/OG).
- Cache: `Cache-Control: public, max-age=86400`.

**Revalidação ISR (`/api/revalidate`):**
- `POST /api/revalidate` com header `Authorization: Bearer {REVALIDATE_SECRET}`.
- Body: `{"tags": ["events-feed"]}`.
- Chama `revalidateTag('events-feed')` do Next.js.
- Retorna `200 {"revalidated": true}` ou `401` se token inválido.

**API de eventos (`/api/events`):**
- `GET /api/events?cursor={iso_date}&category={cat}&limit=20`
- Retorna: `{ events: Event[], nextCursor: string | null, total: number }`
- Consulta a view `public_feed` do Supabase com filtros opcionais.
- Marcada com `unstable_cache` e tag `events-feed`.

**Configuração Cloudflare / OpenNext:**

```
web/
├── wrangler.toml              ← config do Cloudflare Worker
├── open-next.config.ts        ← config do adapter OpenNext
├── next.config.ts             ← sem runtime edge forçado
└── package.json               ← scripts: dev, build, deploy
```

`wrangler.toml` mínimo:
```toml
name = "trump-tracker"
compatibility_date = "2024-12-01"
compatibility_flags = ["nodejs_compat"]
main = ".open-next/worker.js"

[assets]
directory = ".open-next/assets"
binding = "ASSETS"
```

`open-next.config.ts` mínimo:
```typescript
import type { OpenNextConfig } from "@opennextjs/cloudflare";
const config: OpenNextConfig = {};
export default config;
```

Scripts `package.json`:
```json
{
  "dev": "next dev",
  "build": "next build",
  "deploy": "opennextjs-cloudflare build && wrangler deploy",
  "preview": "opennextjs-cloudflare build && wrangler dev"
}
```

**Stack frontend:**
- Next.js 15 App Router
- TailwindCSS v4
- shadcn/ui (componentes: Badge, Button, Tabs, Card, Separator)
- `@supabase/supabase-js` para cliente no servidor
- `@vercel/og` para OG images
- `@opennextjs/cloudflare` + `wrangler` para deploy

**Regras de negócio**

- DEVE usar cursor pagination (não offset) para o feed — offset degrada com volumes grandes.
- DEVE consumir a view `public_feed` (não a tabela `events` diretamente) para excluir eventos mesclados.
- O cache do feed DEVE ser invalidado via tag `events-feed` após cada publicação de novo evento.
- NÃO DEVE expor `SUPABASE_KEY` no cliente — todas as queries ao Supabase são server-side.
- `NEXT_PUBLIC_SITE_URL` é a única variável exposta ao cliente (para construir URLs canônicas e de share).
- O botão de share DEVE usar Web Share API se disponível; fallback: copia URL para clipboard.
- OG images DEVEM ser cacheadas por 24h no CDN.
- DEVE funcionar sem JavaScript para o conteúdo principal (SSR).
- O counter de aberrações DEVE refletir o total real de eventos na view `public_feed`.
- Em desenvolvimento (`npm run dev`): Supabase acessado diretamente via `SUPABASE_URL` e `SUPABASE_KEY` do `.env.local`.

**Critérios de aceite**

- DADO feed com 50+ eventos QUANDO usuário rola até o final ENTÃO próxima página carrega automaticamente.
- DADO filtro "Econômico" ativo QUANDO aplicado ENTÃO apenas eventos dessa categoria são exibidos.
- DADO evento publicado QUANDO `publish_agent` dispara revalidação ENTÃO feed atualiza em < 2h (próximo run).
- DADO URL `/event/{slug}` QUANDO acessada ENTÃO meta tags OG corretas para Twitter Card.
- DADO URL `/api/og?slug={slug}` QUANDO acessada ENTÃO imagem 1200×630 gerada corretamente.
- DADO `POST /api/revalidate` com token inválido QUANDO executado ENTÃO retorna `401`.
- DADO `GET /api/events` QUANDO executado ENTÃO retorna JSON válido com paginação.
- DADO `npm run dev` QUANDO executado ENTÃO feed carrega com dados do Supabase local.
- DADO `npm run deploy` QUANDO executado ENTÃO site acessível em `*.workers.dev` ou domínio customizado.
- DADO LCP no Cloudflare CDN QUANDO medido ENTÃO < 1s (ISR serve do edge).

**Estado atual**
> `web/` não existe. O briefing descreve a estrutura de componentes e rotas mas não contém código frontend.

**Mudanças necessárias**

- **Frontend:** Criar toda a estrutura `web/` do zero.
- **Configuração:** Criar `wrangler.toml`, `open-next.config.ts`, `next.config.ts`.
- **Deploy:** Configurar Cloudflare Pages project apontando para o Worker gerado pelo OpenNext.
- **Variáveis de ambiente Cloudflare:** `SUPABASE_URL`, `SUPABASE_KEY`, `REVALIDATE_SECRET`, `NEXT_PUBLIC_SITE_URL` no dashboard do Cloudflare Pages.

**Definição de pronto**

- [ ] Feed carrega e pagina corretamente em produção
- [ ] Filtros por categoria funcionando
- [ ] Página individual com OG tags corretas
- [ ] OG image gerada e cacheada (verificar via `og:image` validator)
- [ ] Revalidação ISR disparada pelo `publish_agent` e refletida no feed
- [ ] Deploy no Cloudflare via `npm run deploy` funcionando
- [ ] LCP < 1s verificado via Cloudflare Speed test
- [ ] Web Share API funcionando em mobile (iOS Safari, Android Chrome)
- [ ] Código revisado por outro membro do time
- [ ] Documentações `docs/frontend/*.mdx` e `docs/infra/cloudflare.mdx` criadas

---

## SPEC-07 — Backfill Histórico

**Objetivo**
> Implementar `agents/backfill_agent.py` para preencher o feed com eventos históricos (desde a posse em 20/jan/2025), evitando que o feed comece vazio no lançamento.

**Contexto**
> No lançamento, o feed estará vazio. Sem um backfill, a experiência inicial será decepcionante. O backfill_agent estende o `ingest_agent` com janelas de lookback maiores, usa fontes com histórico completo (GDELT, Guardian, Wikipedia), e processa em batches controlados para não explodir os limites das APIs gratuitas.

**Comportamento esperado**

1. Aceita `--from {YYYY-MM-DD}` (default: `2025-01-20`) e `--to {YYYY-MM-DD}` (default: hoje).
2. Aceita `--batch-size N` (default: 50 eventos por dia de processamento).
3. Divide o período em janelas diárias e processa uma janela por vez.
4. Para períodos curtos (< 60 dias): usa `ingest_agent` com `lookback_hours` expandido + NewsAPI.
5. Para períodos médios (60–365 dias): GDELT + Guardian API como fontes primárias.
6. Para períodos longos (> 365 dias): GDELT + Guardian + Wikipedia API como âncora de eventos marcantes.
7. Para períodos longos, usa threshold de dedup mais conservador: similaridade ≥ 0.95 para duplicata (evitar falsos positivos em retrospecção).
8. Imprime progresso por janela processada.

**Seed mínimo obrigatório (MVP):**

Antes ou junto com o backfill automatizado, inserir manualmente 5–10 eventos âncora da posse (20/jan/2025) diretamente na tabela `events`, com fontes primárias Tier 1 verificadas. Esses eventos garantem que o feed não comece vazio mesmo se o backfill demorar.

**Regras de negócio**

- DEVE reutilizar o pipeline completo (ingest → classify → dedup → publish) para cada janela.
- NÃO DEVE ultrapassar os limites das APIs gratuitas (NewsAPI: 30 dias de histórico, 100 req/dia).
- DEVE usar threshold de dedup 0.95 para períodos > 365 dias.
- DEVE ser interrompível e retomável — artigos já no banco são ignorados (dedup por URL do ingest).
- PODE ser executado manualmente: `/tracker backfill --from 2025-01-20` ou via `workflow_dispatch`.
- NÃO DEVE ser incluído no cron automático de 2h.

**Critérios de aceite**

- DADO `--from 2025-01-20 --to 2025-03-01` QUANDO executado ENTÃO artigos do período aparecem no banco.
- DADO artigo já existente no banco QUANDO o backfill passa pela mesma data ENTÃO não é duplicado.
- DADO `--dry-run` QUANDO executado ENTÃO nenhuma escrita no banco.
- DADO período > 365 dias QUANDO processado ENTÃO threshold de dedup é 0.95 (não 0.92).

**Estado atual**
> `agents/backfill_agent.py` não existe. `.claude/skills/trump-tracker/backfill.md` existe como documentação de estratégia.

**Mudanças necessárias**

- **Backend:** Criar `agents/backfill_agent.py`, reutilizando funções do `ingest_agent.py`.
- **Config:** Nenhuma mudança em `sources.yml` — o backfill usa as mesmas fontes com janela expandida.

**Definição de pronto**

- [ ] Backfill desde 20/jan/2025 executado com sucesso
- [ ] Seed de 5–10 eventos âncora inseridos manualmente
- [ ] Nenhum evento duplicado gerado pelo backfill
- [ ] `--dry-run` funcional
- [ ] Código revisado por outro membro do time
- [ ] Documentação `docs/pipeline/backfill.mdx` criada
