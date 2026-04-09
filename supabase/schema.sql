-- supabase/schema.sql
-- Execute no Supabase SQL Editor antes do primeiro run

CREATE EXTENSION IF NOT EXISTS vector;

-- ──────────────────────────────────────────
-- Inbox de tudo que foi ingerido (nunca apagar)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_articles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identificação e dedup
    url          TEXT UNIQUE NOT NULL,
    url_hash     TEXT NOT NULL,         -- sha256[:16] para dedup rápido

    -- Conteúdo
    title        TEXT NOT NULL,
    body         TEXT,                  -- primeiros 2000 chars

    -- Origem
    source_name  TEXT NOT NULL,
    source_tier  SMALLINT DEFAULT 2,    -- 1=primária, 2=referência, 3=suplementar
    raw_query    TEXT,                  -- qual query gerou este artigo

    -- Temporal
    published_at TIMESTAMPTZ NOT NULL,
    fetched_at   TIMESTAMPTZ DEFAULT NOW(),

    -- Pipeline
    status       TEXT DEFAULT 'pending'
                 CHECK (status IN ('pending','classified','rejected','published')),
    priority     BOOLEAN DEFAULT FALSE, -- keywords de alta prioridade no título
    processed_at TIMESTAMPTZ            -- quando o classify_agent processou
);

CREATE INDEX IF NOT EXISTS idx_raw_articles_status
    ON raw_articles (status, priority DESC, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_articles_published
    ON raw_articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_articles_url_hash
    ON raw_articles (url_hash);

-- ──────────────────────────────────────────
-- Feed público (preenchida pelo publish_agent)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug              TEXT UNIQUE NOT NULL,

    -- Conteúdo editorial (pt-BR)
    headline          TEXT NOT NULL,
    summary           TEXT NOT NULL,
    historical_context TEXT,
    tags              JSONB DEFAULT '[]',

    -- Classificação
    score             SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 10),
    score_breakdown   JSONB,            -- {precedent, velocity, inst_impact, system_reaction}
    category          TEXT NOT NULL,
    confidence        TEXT DEFAULT 'high' CHECK (confidence IN ('high','medium','low')),

    -- Fontes
    source_url        TEXT NOT NULL,
    source_name       TEXT NOT NULL,
    source_tier       SMALLINT DEFAULT 2,
    secondary_sources JSONB DEFAULT '[]',

    -- Temporal
    occurred_at       TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),

    -- Engajamento
    share_count       INT DEFAULT 0,
    view_count        INT DEFAULT 0,

    -- Pipeline / revisão
    review_status     TEXT DEFAULT 'auto'
                      CHECK (review_status IN ('auto','human_approved','human_edited')),
    reviewed_by       TEXT,
    merged_into_id    UUID REFERENCES events(id),
    raw_article_id    UUID REFERENCES raw_articles(id),

    -- Semântico
    embedding         vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_events_occurred_at
    ON events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_category
    ON events (category);
CREATE INDEX IF NOT EXISTS idx_events_score
    ON events (score DESC);
CREATE INDEX IF NOT EXISTS idx_events_embedding
    ON events USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- View para o feed público (exclui mesclados/removidos)
CREATE OR REPLACE VIEW public_feed AS
SELECT id, slug, headline, summary, score, category,
       source_url, source_name, secondary_sources,
       occurred_at, historical_context, tags,
       share_count, view_count, review_status
FROM events
WHERE merged_into_id IS NULL
ORDER BY occurred_at DESC;