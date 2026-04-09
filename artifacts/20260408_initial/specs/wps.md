# Trump Tracker — Plano de Execução

> **Versão:** 1.0.0
> **Data:** 2026-04-08
> **Sequencial inicial:** WP-00
> **Specs relacionadas:** `artifacts/20260408_initial/specs/specs.md`

---

## Índice

- [WP-00 — Correções de Fundação](#wp-00--correções-de-fundação)
- [WP-01 — Agente de Classificação IA](#wp-01--agente-de-classificação-ia)
- [WP-02 — Agente de Deduplicação Semântica](#wp-02--agente-de-deduplicação-semântica)
- [WP-03 — Moderação via Telegram](#wp-03--moderação-via-telegram)
- [WP-04 — Agente de Publicação](#wp-04--agente-de-publicação)
- [WP-05 — Orquestração GitHub Actions](#wp-05--orquestração-github-actions)
- [WP-06 — Next.js Scaffold + Config Cloudflare](#wp-06--nextjs-scaffold--config-cloudflare)
- [WP-07 — Feed + Componentes UI](#wp-07--feed--componentes-ui)
- [WP-08 — Página Individual + Engajamento](#wp-08--página-individual--engajamento)
- [WP-09 — OG Images + ISR + Deploy](#wp-09--og-images--isr--deploy)
- [WP-10 — Backfill Histórico](#wp-10--backfill-histórico)
- [Mapa de Dependências](#mapa-de-dependências)
- [Riscos e Pontos Desconhecidos](#riscos-e-pontos-desconhecidos)
- [Oportunidades de Paralelização](#oportunidades-de-paralelização)

---

### WP-00 — Correções de Fundação

| Campo | Valor |
|---|---|
| **ID** | WP-00 |
| **Status** | ✅ Concluído |
| **Spec relacionada** | [SPEC-01](specs.md#spec-01--agente-de-classificação-ia), [SPEC-03](specs.md#spec-03--moderação-via-telegram), [SPEC-04](specs.md#spec-04--agente-de-publicação), [SPEC-05](specs.md#spec-05--orquestração-cicd) |
| **Estimativa** | 0.5d |
| **Dependências** | Nenhuma |
| **Pode paralelizar com** | WP-06 |

**Escopo**

Corrige todas as inconsistências de fundação identificadas no briefing antes que qualquer agent seja implementado. Entrega: schema corrigido, colunas de classificação adicionadas, `sources.example.yml` criado, e `requirements.txt` com dependências descomentadas.

**Passos sugeridos de implementação**

1. Atualizar `supabase/schema.sql` — corrigir o CHECK constraint de `raw_articles.status`:
   ```sql
   CHECK (status IN (
     'pending', 'classified', 'rejected',
     'approved', 'approved_manual',
     'pending_review', 'published'
   ))
   ```
2. Adicionar colunas de classificação à tabela `raw_articles` no schema:
   ```sql
   ALTER TABLE raw_articles
     ADD COLUMN IF NOT EXISTS headline_pt        TEXT,
     ADD COLUMN IF NOT EXISTS summary_pt         TEXT,
     ADD COLUMN IF NOT EXISTS historical_context TEXT,
     ADD COLUMN IF NOT EXISTS score              SMALLINT,
     ADD COLUMN IF NOT EXISTS score_breakdown    JSONB,
     ADD COLUMN IF NOT EXISTS category           TEXT,
     ADD COLUMN IF NOT EXISTS confidence         TEXT,
     ADD COLUMN IF NOT EXISTS needs_human_review BOOLEAN DEFAULT FALSE;
   ```
3. Executar o schema atualizado no Supabase SQL Editor (substituir o schema existente ou aplicar as alterações via migration script).
4. Criar `config/sources.example.yml` como cópia de `config/sources.yml` com comentários explicativos (queries e feeds são exemplos válidos para qualquer fork).
5. Descomentar em `requirements.txt`:
   - `anthropic==0.28.0` (ou versão mais recente com suporte a Prompt Caching)
   - `openai==1.30.0`
6. Verificar que `.gitignore` inclui `.env` e não inclui `config/sources.yml` (fontes são config, não secret).

**Critérios de aceite do pacote**

- [ ] Schema aplicado no Supabase sem erros
- [ ] `INSERT INTO raw_articles (status) VALUES ('approved')` executa sem erro de constraint
- [ ] `INSERT INTO raw_articles (status) VALUES ('approved_manual')` executa sem erro de constraint
- [ ] `INSERT INTO raw_articles (status) VALUES ('pending_review')` executa sem erro de constraint
- [ ] `INSERT INTO raw_articles (headline_pt, summary_pt, score) VALUES (...)` executa sem erro
- [ ] `config/sources.example.yml` existe e tem estrutura idêntica ao `sources.yml`
- [ ] `pip install -r requirements.txt` instala anthropic e openai sem erros

**Áreas impactadas**
> [banco] `supabase/schema.sql` | [config] `config/sources.example.yml` | [backend] `requirements.txt`

---

### WP-01 — Agente de Classificação IA

| Campo | Valor |
|---|---|
| **ID** | WP-01 |
| **Status** | ✅ Concluído |
| **Spec relacionada** | [SPEC-01](specs.md#spec-01--agente-de-classificação-ia) |
| **Estimativa** | 2d |
| **Dependências** | WP-00 |
| **Pode paralelizar com** | — |

**Escopo**

Implementa `agents/classify_agent.py` completo: lê artigos `pending`, classifica em batches de 5 via Claude Sonnet com Prompt Caching, e roteia por score (≤3 → rejected, 4–7 → classified, ≥8 → needs_human_review).

**Passos sugeridos de implementação**

1. Criar `agents/classify_agent.py` com a estrutura de funções:
   - `fetch_pending_articles(supabase, limit=50) → list[dict]`
   - `build_system_prompt() → str` — system prompt completo com rubrica do Aberration Score, categorias, e padrões de headline/summary. Este prompt deve ser marcado para caching.
   - `build_classification_prompt(articles: list[dict]) → str` — user prompt com os 5 artigos como JSON array (body truncado para 800 chars).
   - `classify_batch(client, articles) → list[dict]` — chama a API Anthropic, parseia JSON da resposta.
   - `route_by_score(result: dict) → str` — retorna novo status baseado em score e confidence.
   - `update_articles(supabase, results: list[dict])` — UPDATE em batch no banco.
   - `main()` — orquestra tudo, aceita `--dry-run` e `--limit`.
2. Implementar o system prompt com a rubrica completa (4 dimensões, tabela de referência, categorias canônicas, padrão de headline e summary) conforme `.claude/skills/trump-tracker/_shared.md`.
3. Implementar Prompt Caching via `anthropic.beta.prompt_caching` — marcar o system prompt com `{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}`.
4. Implementar tratamento de erro de JSON inválido: se a resposta do Claude não for JSON válido, logar o erro, não atualizar os artigos do batch, e continuar com o próximo.
5. Testar localmente com `--dry-run --limit 5`.

**Critérios de aceite do pacote**

- [ ] `python agents/classify_agent.py --dry-run` executa sem erro com banco acessível
- [ ] Artigos com score ≤ 3 ficam com `status='rejected'` após execução real
- [ ] Artigos com score 4–7 ficam com `status='classified'` e todos os campos preenchidos
- [ ] Artigos com score ≥ 8 ficam com `status='classified'` e `needs_human_review=TRUE`
- [ ] Log mostra "1 chamada ao Claude para 5 artigos" (não 5 chamadas)
- [ ] Resposta da API Anthropic inclui `cache_creation_input_tokens > 0` na primeira chamada

**Áreas impactadas**
> [backend] `agents/classify_agent.py` | [requirements] `requirements.txt` | [banco] tabela `raw_articles`

---

### WP-02 — Agente de Deduplicação Semântica

| Campo | Valor |
|---|---|
| **ID** | WP-02 |
| **Spec relacionada** | [SPEC-02](specs.md#spec-02--agente-de-deduplicação-semântica) |
| **Estimativa** | 1d |
| **Dependências** | WP-01 |
| **Pode paralelizar com** | WP-03 |

**Escopo**

Implementa `agents/dedup_agent.py`: gera embeddings dos artigos classificados, consulta pgvector, aplica a tabela de decisão por similaridade cosine, e roteia cada artigo para `approved`, `rejected` ou `merged`.

**Passos sugeridos de implementação**

1. Criar `agents/dedup_agent.py` com as funções:
   - `fetch_classified_articles(supabase) → list[dict]` — WHERE `status='classified'` AND `needs_human_review=false`
   - `generate_embedding(openai_client, text: str) → list[float]` — via `text-embedding-3-small`
   - `find_similar_events(supabase, embedding, limit=5) → list[dict]` — query pgvector com `<=>` cosine distance
   - `decide_action(article, similar_events) → tuple[str, uuid | None]` — aplica tabela de decisão
   - `apply_decision(supabase, article_id, action, merged_into_id) → None`
   - `enrich_secondary_sources(supabase, event_id, new_source_url, new_source_name) → None`
   - `main()` — orquestra, aceita `--dry-run`
2. Implementar a query pgvector no Supabase usando RPC ou SQL direto:
   ```sql
   SELECT id, slug, occurred_at, embedding <=> $1::vector AS distance
   FROM events
   WHERE merged_into_id IS NULL
   ORDER BY distance ASC
   LIMIT 5
   ```
3. Implementar a lógica de update vs. duplicata para a faixa 0.80–0.91 (ver [SPEC-02](specs.md#spec-02--agente-de-deduplicação-semântica)).
4. Para artigos relacionados (0.65–0.79): adicionar URL ao campo `secondary_sources` do evento mais similar via `jsonb_set`.
5. Testar com `--dry-run` e verificar decisões no log.

**Critérios de aceite do pacote**

- [ ] `python agents/dedup_agent.py --dry-run` executa sem erro
- [ ] Dois artigos com similaridade ≥ 0.92: apenas um com `status='approved'`, outro `rejected`
- [ ] Artigo com similaridade < 0.65: `status='approved'`
- [ ] Artigo com similaridade 0.80–0.91 e `occurred_at` > 2h + termo "reverses": `status='approved'`
- [ ] Nenhum registro deletado (verificar COUNT da tabela antes/depois)

**Áreas impactadas**
> [backend] `agents/dedup_agent.py` | [banco] tabelas `raw_articles`, `events`

---

### WP-03 — Moderação via Telegram

| Campo | Valor |
|---|---|
| **ID** | WP-03 |
| **Spec relacionada** | [SPEC-03](specs.md#spec-03--moderação-via-telegram) |
| **Estimativa** | 1.5d |
| **Dependências** | WP-01 |
| **Pode paralelizar com** | WP-02 |

**Escopo**

Implementa `agents/telegram_agent.py` (envia cards de revisão) e `cloudflare/telegram-webhook.js` (processa callbacks de aprovação/rejeição). Inclui deploy do Worker e configuração do webhook.

**Passos sugeridos de implementação**

1. Criar `agents/telegram_agent.py`:
   - `fetch_review_pending(supabase) → list[dict]` — WHERE `status='classified'` AND `needs_human_review=true`
   - `build_card(article) → str` — mensagem formatada conforme [SPEC-03](specs.md#spec-03--moderação-via-telegram)
   - `build_keyboard(article_id) → dict` — inline keyboard com 2 botões: `publish:{id}` e `reject:{id}`
   - `send_card(httpx_client, article) → bool` — POST para `sendMessage` da Bot API
   - `mark_pending_review(supabase, article_ids) → None` — UPDATE `status='pending_review'`
   - `main()` — orquestra, aceita `--dry-run`
2. Criar `cloudflare/telegram-webhook.js` conforme [SPEC-03](specs.md#spec-03--moderação-via-telegram):
   - Handler de `callback_query` com actions `publish` e `reject`
   - Chamada REST ao Supabase para atualizar status
   - `answerCallbackQuery` para confirmação ao Telegram
   - Retorno 200 em todos os casos (evitar retry do Telegram)
3. Criar `cloudflare/wrangler.toml` para o Worker:
   ```toml
   name = "trump-tracker-telegram-webhook"
   main = "telegram-webhook.js"
   compatibility_date = "2024-12-01"
   ```
4. Fazer deploy do Worker: `cd cloudflare && wrangler deploy`.
5. Configurar secrets do Worker: `wrangler secret put SUPABASE_URL`, `SUPABASE_KEY`, `TELEGRAM_BOT_TOKEN`.
6. Configurar webhook URL via API:
   ```bash
   curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
     -d "url=https://trump-tracker-telegram-webhook.{account}.workers.dev"
   ```
7. Testar end-to-end: rodar `telegram_agent.py` com artigo real e clicar nos botões.

**Critérios de aceite do pacote**

- [ ] Card de moderação chega ao TELEGRAM_CHAT_ID com formato correto
- [ ] Card tem exatamente 2 botões: ✅ Publicar e ❌ Rejeitar (sem Editar)
- [ ] Clique em Publicar → `status='approved_manual'` no banco
- [ ] Clique em Rejeitar → `status='rejected'` no banco
- [ ] Worker responde ao Telegram em < 2s (verificar no dashboard do Cloudflare)
- [ ] `python agents/telegram_agent.py --dry-run` executa sem enviar mensagem

**Áreas impactadas**
> [backend] `agents/telegram_agent.py` | [integrações] `cloudflare/telegram-webhook.js`, `cloudflare/wrangler.toml` | [banco] tabela `raw_articles`

---

### WP-04 — Agente de Publicação

| Campo | Valor |
|---|---|
| **ID** | WP-04 |
| **Spec relacionada** | [SPEC-04](specs.md#spec-04--agente-de-publicação) |
| **Estimativa** | 1d |
| **Dependências** | WP-02, WP-03 |
| **Pode paralelizar com** | — |

**Escopo**

Implementa `agents/publish_agent.py`: transforma artigos aprovados em eventos públicos na tabela `events`, gerando embedding, slug único, e disparando revalidação do cache Next.js.

**Passos sugeridos de implementação**

1. Criar `agents/publish_agent.py` com as funções:
   - `fetch_approved(supabase) → list[dict]` — WHERE `status IN ('approved', 'approved_manual')`
   - `generate_embedding(openai_client, article) → list[float]`
   - `generate_slug(headline_pt, occurred_at, supabase) → str` — kebab, unidecode, anti-colisão
   - `build_event_row(article, embedding, slug) → dict` — mapeamento conforme [SPEC-04](specs.md#spec-04--agente-de-publicação)
   - `insert_event(supabase, row) → bool` — INSERT com ON CONFLICT (slug) DO NOTHING
   - `mark_published(supabase, article_id) → None`
   - `trigger_revalidation(httpx_client) → None` — POST /api/revalidate
   - `main()` — orquestra, aceita `--dry-run`
2. Implementar geração de slug:
   ```python
   from unidecode import unidecode
   import re
   slug_base = re.sub(r'[^a-z0-9-]', '', unidecode(headline_pt).lower().replace(' ', '-'))[:60]
   slug = f"{slug_base}-{occurred_at.strftime('%Y-%m-%d')}"
   # Anti-colisão: SELECT COUNT(*) WHERE slug LIKE '{slug}%'
   ```
3. Implementar mapeamento de `review_status`: `'approved'` → `'auto'`, `'approved_manual'` → `'human_approved'`.
4. Testar com `--dry-run` e verificar o slug gerado no log.
5. Testar revalidação apontando para URL do Cloudflare Pages (pode ser `localhost:3000/api/revalidate` em dev).

**Critérios de aceite do pacote**

- [ ] Artigo `approved` resulta em evento na tabela `events` com todos os campos
- [ ] Artigo `approved_manual` resulta em evento com `review_status='human_approved'`
- [ ] Slug gerado em kebab-case sem acentos: `trump-demite-diretor-fbi-2025-03-15`
- [ ] Dois artigos com mesmo slug calculado: segundo recebe sufixo `-2`
- [ ] `ON CONFLICT (slug) DO NOTHING` testado (re-executar não duplica)
- [ ] Revalidação disparada após batch (log mostra POST /api/revalidate)
- [ ] `--dry-run` sem escrita no banco

**Áreas impactadas**
> [backend] `agents/publish_agent.py` | [banco] tabelas `raw_articles`, `events` | [integrações] Next.js `/api/revalidate`

---

### WP-05 — Orquestração GitHub Actions

| Campo | Valor |
|---|---|
| **ID** | WP-05 |
| **Spec relacionada** | [SPEC-05](specs.md#spec-05--orquestração-cicd) |
| **Estimativa** | 0.5d |
| **Dependências** | WP-04 |
| **Pode paralelizar com** | WP-06, WP-07 |

**Escopo**

Cria `.github/workflows/pipeline.yml` com cron de 2h, sequenciamento dos 5 agents, mapeamento de todos os secrets, e suporte a `workflow_dispatch` com inputs.

**Passos sugeridos de implementação**

1. Criar `.github/workflows/pipeline.yml` conforme [SPEC-05](specs.md#spec-05--orquestração-cicd) e o YAML de referência no briefing (seção 5).
2. Configurar os 10 secrets no GitHub (Settings → Secrets → Actions): `SUPABASE_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NEWSAPI_KEY`, `GUARDIAN_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `REVALIDATE_SECRET`, `NEXT_PUBLIC_SITE_URL`.
3. Testar via `workflow_dispatch` com `dry_run=true` antes de ativar o cron.
4. Verificar que o pipeline completo termina em < 20 minutos (timeout configurado).

**Critérios de aceite do pacote**

- [ ] `workflow_dispatch` com `dry_run=true` completa sem erros (todos os 5 steps passam)
- [ ] Cron dispara automaticamente e aparece no histórico de Actions
- [ ] Falha no `classify_agent` impede execução dos steps seguintes
- [ ] Logs de cada step mostram relatório do respectivo agent

**Áreas impactadas**
> [config/env] `.github/workflows/pipeline.yml` | [CI/CD] GitHub Actions secrets

---

### WP-06 — Next.js Scaffold + Config Cloudflare

| Campo | Valor |
|---|---|
| **ID** | WP-06 |
| **Spec relacionada** | [SPEC-06](specs.md#spec-06--frontend-público) |
| **Estimativa** | 2d |
| **Dependências** | Nenhuma |
| **Pode paralelizar com** | WP-00, WP-05 |

**Escopo**

Cria a estrutura base do `web/`: Next.js 15 App Router com TailwindCSS e shadcn/ui, cliente Supabase server-side, configuração completa do `@opennextjs/cloudflare` para deploy no Cloudflare Workers, e API route de eventos com cursor pagination.

**Passos sugeridos de implementação**

1. Inicializar o projeto:
   ```bash
   cd web
   npx create-next-app@latest . --typescript --tailwind --app --no-src-dir
   npx shadcn@latest init
   npx shadcn@latest add badge button tabs card separator
   npm install @supabase/supabase-js @opennextjs/cloudflare wrangler
   ```
2. Criar `web/lib/supabase.ts` — cliente server-side usando `SUPABASE_URL` e `SUPABASE_KEY` (sem expor ao browser).
3. Criar `web/app/api/events/route.ts` com cursor pagination:
   - `GET /api/events?cursor={iso}&category={cat}&limit=20`
   - Consulta a view `public_feed` do Supabase
   - Marcado com `unstable_cache` e tag `events-feed`
   - Retorna `{ events, nextCursor, total }`
4. Criar `web/wrangler.toml` conforme [SPEC-06](specs.md#spec-06--frontend-público).
5. Criar `web/open-next.config.ts` conforme [SPEC-06](specs.md#spec-06--frontend-público).
6. Configurar `web/next.config.ts` — sem `runtime: 'edge'` forçado (OpenNext não exige).
7. Criar `web/.env.local.example` com `SUPABASE_URL`, `SUPABASE_KEY`, `NEXT_PUBLIC_SITE_URL`, `REVALIDATE_SECRET`.
8. Verificar `npm run dev` com dados reais do Supabase.
9. Verificar `npm run preview` (build OpenNext + `wrangler dev`) funcionando localmente.

**Critérios de aceite do pacote**

- [ ] `npm run dev` inicia sem erros e `/api/events` retorna dados do Supabase
- [ ] `GET /api/events?limit=5` retorna JSON com estrutura correta `{ events, nextCursor, total }`
- [ ] `npm run preview` (wrangler dev) funciona localmente
- [ ] `npm run deploy` faz build e deploy para Cloudflare Workers sem erros

**Áreas impactadas**
> [frontend] `web/` (estrutura completa) | [config] `wrangler.toml`, `open-next.config.ts`, `next.config.ts` | [integrações] Supabase, Cloudflare

---

### WP-07 — Feed + Componentes UI

| Campo | Valor |
|---|---|
| **ID** | WP-07 |
| **Spec relacionada** | [SPEC-06](specs.md#spec-06--frontend-público) |
| **Estimativa** | 2d |
| **Dependências** | WP-06 |
| **Pode paralelizar com** | — |

**Escopo**

Implementa os componentes visuais do feed: `EventCard.tsx`, `AberrationBadge.tsx`, `CategoryFilter.tsx` (tabs), scroll infinito com Intersection Observer, e counter de aberrações no header.

**Passos sugeridos de implementação**

1. Criar `web/components/AberrationBadge.tsx`:
   - Props: `score: number`
   - Cores semânticas por faixa: 1–3 cinza, 4–5 amarelo, 6–7 laranja, 8–9 vermelho, 10 vermelho-escuro
   - Exibe: `Score {N}/10` com ícone de barômetro ou similar
2. Criar `web/components/EventCard.tsx`:
   - Props: `event: Event` (tipo derivado da view `public_feed`)
   - Layout: AberrationBadge + emoji de categoria + headline (2 linhas max) + data + fonte linkada
   - Link para `/event/{slug}`
3. Criar `web/components/CategoryFilter.tsx`:
   - shadcn Tabs com as 8 categorias + "Todos"
   - Atualiza parâmetro de query na URL sem reload (Next.js `useRouter().push`)
4. Criar `web/app/page.tsx`:
   - Server Component que carrega a primeira página (20 eventos) para SSR
   - Passa dados iniciais para o Client Component de scroll infinito
5. Criar `web/components/InfiniteScroll.tsx` (Client Component):
   - Usa `useRef` + `IntersectionObserver` para detectar fim da lista
   - Quando sentinel visível: fetch `/api/events?cursor={nextCursor}&category={cat}`
   - Acumula eventos no estado local
6. Adicionar counter de aberrações no `web/app/layout.tsx` (header):
   - Server Component que busca `total` via `/api/events?limit=1`
   - Exibe "X aberrações desde a posse"

**Critérios de aceite do pacote**

- [ ] Feed carrega com 20 eventos na primeira renderização (SSR)
- [ ] Ao rolar até o fim, próxima página é carregada automaticamente
- [ ] Filtro por categoria funciona sem reload de página
- [ ] Counter no header exibe número correto de eventos
- [ ] `AberrationBadge` exibe cor correta para cada faixa de score
- [ ] Links dos cards apontam para `/event/{slug}`

**Áreas impactadas**
> [frontend] `web/app/page.tsx`, `web/components/` (EventCard, AberrationBadge, CategoryFilter, InfiniteScroll), `web/app/layout.tsx`

---

### WP-08 — Página Individual + Engajamento

| Campo | Valor |
|---|---|
| **ID** | WP-08 |
| **Spec relacionada** | [SPEC-06](specs.md#spec-06--frontend-público) |
| **Estimativa** | 1d |
| **Dependências** | WP-07 |
| **Pode paralelizar com** | — |

**Escopo**

Implementa `/event/[slug]` com detalhes completos do evento, score breakdown visual, meta tags OG (apontando para `/api/og`), e botão de compartilhamento nativo com fallback para clipboard.

**Passos sugeridos de implementação**

1. Criar `web/app/event/[slug]/page.tsx` (Server Component):
   - Busca evento por slug via Supabase
   - Se slug não encontrado: `notFound()`
   - Gera metadata com `generateMetadata()`:
     ```typescript
     export async function generateMetadata({ params }) {
       return {
         title: event.headline,
         description: event.summary,
         openGraph: {
           images: [`${NEXT_PUBLIC_SITE_URL}/api/og?slug=${params.slug}`],
         },
       };
     }
     ```
2. Criar layout da página: headline, AberrationBadge, data, fonte linkada, summary, historical_context, score breakdown visual (4 barras ou badges por dimensão).
3. Criar `web/components/ShareButton.tsx` (Client Component):
   - Tenta `navigator.share({ title, url })` (Web Share API)
   - Fallback: `navigator.clipboard.writeText(url)` + toast "Link copiado!"
4. Criar `web/components/ScoreBreakdown.tsx`:
   - Exibe as 4 dimensões do score: Precedente (0–4), Velocidade (0–2), Impacto Institucional (0–2), Reação (0–2)
   - Visual: barra de progresso ou badges por dimensão

**Critérios de aceite do pacote**

- [ ] `/event/{slug}` carrega com todos os detalhes do evento
- [ ] `og:image` na meta tag aponta para `/api/og?slug={slug}`
- [ ] Score breakdown exibe as 4 dimensões com valores corretos
- [ ] Botão share abre Web Share API no mobile; copia URL no desktop
- [ ] Slug inválido retorna 404
- [ ] "← Voltar" leva de volta ao feed

**Áreas impactadas**
> [frontend] `web/app/event/[slug]/page.tsx`, `web/components/ShareButton.tsx`, `web/components/ScoreBreakdown.tsx`

---

### WP-09 — OG Images + ISR + Deploy

| Campo | Valor |
|---|---|
| **ID** | WP-09 |
| **Spec relacionada** | [SPEC-06](specs.md#spec-06--frontend-público) |
| **Estimativa** | 1.5d |
| **Dependências** | WP-08 |
| **Pode paralelizar com** | WP-10 |

**Escopo**

Implementa `/api/og` para geração dinâmica de OG images, `/api/revalidate` para ISR tag-based, e realiza o deploy final em produção no Cloudflare Pages.

**Passos sugeridos de implementação**

1. Criar `web/app/api/og/route.tsx`:
   ```typescript
   import { ImageResponse } from '@vercel/og';
   export const runtime = 'edge'; // necessário para @vercel/og
   export async function GET(request: Request) {
     const { searchParams } = new URL(request.url);
     const slug = searchParams.get('slug');
     // Buscar evento do Supabase pelo slug
     // Retornar ImageResponse com layout 1200×630
   }
   ```
   - Layout: fundo preto, headline branca (max 2 linhas), badge de score em vermelho, nome do site
   - `Cache-Control: public, max-age=86400`
2. Criar `web/app/api/revalidate/route.ts`:
   ```typescript
   import { revalidateTag } from 'next/cache';
   export async function POST(request: Request) {
     const auth = request.headers.get('Authorization');
     if (auth !== `Bearer ${process.env.REVALIDATE_SECRET}`) {
       return Response.json({ error: 'Unauthorized' }, { status: 401 });
     }
     revalidateTag('events-feed');
     return Response.json({ revalidated: true });
   }
   ```
3. Marcar a API route de eventos com a tag correta:
   ```typescript
   const data = await unstable_cache(fetchEvents, ['events'], {
     tags: ['events-feed'],
   })();
   ```
4. Configurar variáveis de ambiente no Cloudflare Pages dashboard: `SUPABASE_URL`, `SUPABASE_KEY`, `REVALIDATE_SECRET`, `NEXT_PUBLIC_SITE_URL`.
5. Deploy em produção: `npm run deploy` (build OpenNext + wrangler deploy).
6. Configurar domínio customizado no Cloudflare Pages (opcional para MVP).
7. Testar OG image via validator (ex: opengraph.xyz).
8. Testar revalidação ponta-a-ponta: `publish_agent.py --dry-run` → verificar POST para `/api/revalidate`.

**Critérios de aceite do pacote**

- [ ] `/api/og?slug={slug}` retorna imagem PNG 1200×630 com headline e score
- [ ] `Cache-Control: public, max-age=86400` presente no header da OG image
- [ ] `POST /api/revalidate` com token correto retorna `{"revalidated": true}`
- [ ] `POST /api/revalidate` com token errado retorna `401`
- [ ] Site acessível em produção no Cloudflare Workers URL
- [ ] OG image validada no opengraph.xyz sem erros
- [ ] LCP < 1s medido via Cloudflare Speed Test

**Áreas impactadas**
> [frontend] `web/app/api/og/route.tsx`, `web/app/api/revalidate/route.ts` | [config] Cloudflare Pages dashboard | [integrações] `@vercel/og`, deploy Cloudflare

---

### WP-10 — Backfill Histórico

| Campo | Valor |
|---|---|
| **ID** | WP-10 |
| **Spec relacionada** | [SPEC-07](specs.md#spec-07--backfill-histórico) |
| **Estimativa** | 2d |
| **Dependências** | WP-05 |
| **Pode paralelizar com** | WP-09 |

**Escopo**

Implementa `agents/backfill_agent.py` com suporte a janelas históricas desde a posse (20/jan/2025), estratégia por período, e threshold de dedup conservador para retrospecção. Inclui inserção manual dos eventos âncora de MVP.

**Passos sugeridos de implementação**

1. Criar `agents/backfill_agent.py`:
   - `parse_args()` — aceita `--from`, `--to`, `--batch-size`, `--dry-run`
   - `generate_daily_windows(from_date, to_date) → list[tuple]` — divide período em janelas de 1 dia
   - `process_window(date, config)` — chama as funções de ingest adaptadas para a data
   - `determine_strategy(from_date, to_date) → str` — "short" / "medium" / "long"
   - `main()` — orquestra por janela com progresso
2. Reutilizar as funções `fetch_gdelt`, `fetch_guardian`, `fetch_rss` do `ingest_agent.py` (importar, não copiar).
3. Para estratégia "long" (> 365 dias): integrar Wikipedia API como âncora de eventos marcantes:
   ```
   GET https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=Trump+{YYYY-MM-DD}
   ```
4. Para estratégia "long": passar `dedup_threshold=0.95` para o `dedup_agent` (adicionar parâmetro `--dedup-threshold` no dedup_agent).
5. Inserir manualmente os 5–10 eventos âncora da posse (20/jan/2025) diretamente em `events` via SQL no Supabase, com fontes Tier 1 verificadas (AP, Reuters, C-SPAN).
6. Testar o backfill de 30 dias com `--dry-run` para validar volume e custos estimados.

**Critérios de aceite do pacote**

- [ ] `python agents/backfill_agent.py --from 2025-01-20 --to 2025-02-20 --dry-run` executa sem erro
- [ ] Ao menos 5 eventos âncora da posse inseridos manualmente na tabela `events`
- [ ] Backfill de 30 dias executado sem duplicatas (verificar UNIQUE em URL)
- [ ] Estratégia "long" usa threshold 0.95 (verificar log)
- [ ] `--dry-run` não escreve no banco

**Áreas impactadas**
> [backend] `agents/backfill_agent.py`, `agents/dedup_agent.py` (adição de `--dedup-threshold`) | [banco] tabela `events` (seed manual)

---

## Mapa de Dependências

```
WP-00 (fundação)
  │
  ├──→ WP-01 (classify)
  │       │
  │       ├──→ WP-02 (dedup) ──────────────────→ WP-04 (publish) → WP-05 (GH Actions) → WP-10 (backfill)
  │       │                                     ↗
  │       └──→ WP-03 (telegram + webhook) ─────
  │
  └── (paralelo) ──→ WP-06 (Next.js scaffold)
                        │
                        └──→ WP-07 (feed + UI)
                                │
                                └──→ WP-08 (event page)
                                        │
                                        └──→ WP-09 (OG + deploy) ← (paralelo com WP-10)
```

**Legenda de fases:**
- **Fase 1** (pipeline backend): WP-00 → WP-01 → WP-02 / WP-03 → WP-04 → WP-05
- **Fase 2** (frontend): WP-06 → WP-07 → WP-08 → WP-09
- **Fase 3** (backfill): WP-10

---

## Riscos e Pontos Desconhecidos

| # | Descrição | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| R01 | Calibração do Aberration Score inconsistente nas primeiras semanas — sem base histórica, o Claude pode calibrar scores acima ou abaixo do esperado | Alta | Médio | Seed manual de 5–10 eventos âncora (WP-10) como referência; revisar distribuição após 30 eventos aprovados via Telegram |
| R02 | GDELT API com instabilidade (timeouts frequentes) | Média | Baixo | Já tratado no `ingest_agent` com `return_exceptions=True`; pipeline não para; GDELT é suplementar, não primário |
| R03 | Free tier do Supabase (50k req/dia) insuficiente em caso de tráfego viral no feed | Baixa | Alto | ISR no Cloudflare reduz drasticamente os requests ao Supabase; monitorar dashboard Supabase antes de migrar para Pro |
| R04 | `@opennextjs/cloudflare` ainda em desenvolvimento ativo; breaking changes ocasionais | Média | Médio | Fixar versão no `package.json`; MVP usa apenas App Router básico + route handlers sem features experimentais |
| R05 | Webhook Telegram exige URL pública antes do primeiro run do `telegram_agent` — sem URL, callbacks não chegam | Alta | Médio | Deploy do Worker (WP-03) é pré-requisito explícito antes de testar o fluxo end-to-end; documentado nos passos do WP-03 |
| R06 | `@vercel/og` em ambiente Cloudflare Workers: compatibilidade com a versão do OpenNext usada | Média | Médio | Testar `/api/og` em `wrangler dev` (preview local) antes do deploy de produção; alternativa: usar `satori` diretamente se `@vercel/og` não funcionar |
| R07 | Artigos do GDELT podem não ter corpo (`body`), apenas título e data — classificação com 800 chars pode ser insuficiente | Alta | Baixo | O classify_agent trunca o corpo disponível; headline + título já contém sinal suficiente para o Claude; explicitado no system prompt |

---

## Oportunidades de Paralelização

| Grupo | WPs | Pré-requisito comum |
|---|---|---|
| G1 | WP-00 e WP-06 | Nenhum — podem iniciar simultaneamente (times diferentes) |
| G2 | WP-02 e WP-03 | WP-01 concluído |
| G3 | WP-05 e WP-07 | WP-04 (para WP-05) e WP-06 (para WP-07) respectivamente |
| G4 | WP-09 e WP-10 | WP-08 (para WP-09) e WP-05 (para WP-10) respectivamente |

**Estratégia de alocação para dois desenvolvedores:**

```
Dev A: WP-00 → WP-01 → WP-02/WP-03* → WP-04 → WP-05 → WP-10
Dev B: WP-06 → WP-07 → WP-08 → WP-09

* WP-02 e WP-03 podem ser divididos entre os devs após WP-01
```

Com dois devs, a Fase 1 e Fase 2 podem rodar em paralelo do início.
Estimativa total: ~8 dias com 1 dev, ~5 dias com 2 devs em paralelo.
