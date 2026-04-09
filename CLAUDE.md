# Trump Tracker — AI Aberration Feed

## O que é isso

Pipeline de inteligência artificial que monitora, classifica e publica automaticamente
eventos inusitados, aberrantes ou sem precedentes históricos envolvendo Donald Trump.

O resultado é um feed web em scroll infinito — reverse-chronological — onde cada card
tem headline impactante, categoria, Aberration Score (1–10) e botão de share com OG
image dinâmica.

Não é um site de opinião. É um arquivo factual, baseado em fontes verificáveis,
com IA avaliando o grau de inusitado de cada evento em relação à norma histórica
da presidência americana.

---

## First Run — Onboarding

Antes de qualquer coisa, verifique silenciosamente se o sistema está configurado.
Execute esses checks toda vez que uma sessão começar:

1. Existe `.env` com as API keys necessárias?
2. Existe `config/sources.yml`?
3. O banco de dados Supabase está acessível?

Se algum desses estiver faltando, entre em modo onboarding.

### Passo 1: API Keys (obrigatório)

Se `.env` estiver faltando ou incompleto, pergunte:

> "Preciso das seguintes chaves para o sistema funcionar:
> - NEWSAPI_KEY — newsapi.org (free tier)
> - GUARDIAN_API_KEY — open-platform.theguardian.com (free)
> - ANTHROPIC_API_KEY — classificação inteligente
> - SUPABASE_URL + SUPABASE_KEY — banco de dados
> - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID — moderação
> - OPENAI_API_KEY — embeddings para dedup
> Quais você já tem?"

### Passo 2: Fontes

Copie `config/sources.example.yml` → `config/sources.yml`.

### Passo 3: Banco de dados

Execute `supabase/schema.sql` no Supabase SQL Editor.

### Passo 4: Pronto

> "Sistema configurado! Comandos disponíveis:
> - /tracker ingest — buscar eventos das últimas 2h
> - /tracker classify — classificar pendentes
> - /tracker publish — publicar aprovados
> - /tracker status — painel de métricas
> - /tracker backfill [dias] — histórico"

---

## Skill Modes

| Se o usuário...              | Modo       |
|------------------------------|------------|
| Pede /tracker ingest         | ingest     |
| Pede /tracker classify       | classify   |
| Pede /tracker publish        | publish    |
| Pede /tracker status         | status     |
| Pede /tracker backfill       | backfill   |
| Cola URL ou texto de notícia | auto-pipeline |

---

## Princípios editoriais — CRÍTICOS

Este sistema classifica, não opina. O Aberration Score mede desvio histórico
da norma presidencial americana — não aprovação ou desaprovação política.

### Regras de publicação

1. NUNCA publique sem pelo menos 1 fonte verificável Tier 1 ou 2
2. SEMPRE link para a fonte primária — não o agregador
3. Separe fato de interpretação. A headline descreve o que aconteceu
4. Human-in-the-loop OBRIGATÓRIO para score ≥ 8 via Telegram
5. Dedup obrigatório. Mesmo evento com múltiplas coberturas = 1 card

---

## Convenções técnicas

- Python 3.12, asyncio, httpx (async), Pydantic v2
- Supabase (Postgres + pgvector) — toda persistência
- Next.js 15 App Router, TailwindCSS, shadcn/ui
- GitHub Actions para cron (a cada 2h)
- Cloudflare Pages para frontend + Worker para webhook Telegram
- NUNCA arquivos .jsonl ou .tsv em produção — tudo no banco