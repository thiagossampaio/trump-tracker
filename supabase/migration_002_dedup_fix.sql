-- ──────────────────────────────────────────────────────────────────────────
-- Migration 002 — Correção do dedup intra-lote
-- ──────────────────────────────────────────────────────────────────────────
-- Contexto: o dedup_agent compara artigos apenas contra a tabela events.
-- Quando N cópias da mesma notícia (syndication) chegam no mesmo ciclo,
-- nenhuma virou evento ainda e todas passam como independentes.
--
-- Esta migração adiciona:
--   1. raw_articles.embedding — gerado no dedup e reutilizado pelo publish
--      (elimina regeneração com texto inconsistente e custo 2x de API)
--   2. raw_articles.duplicate_of_article_id — FK para o artigo canônico do
--      MESMO lote (merged_into_id não serve: referencia events(id), e o
--      canônico ainda não é evento no momento da decisão). O publish_agent
--      fecha a linhagem: ao publicar o canônico, seta merged_into_id dos
--      duplicados para o evento criado e agrega suas fontes em
--      secondary_sources.
--
-- 100% aditiva — segura para aplicar antes do deploy do código.
-- Executar no Supabase SQL Editor.
-- ──────────────────────────────────────────────────────────────────────────

ALTER TABLE raw_articles
  ADD COLUMN IF NOT EXISTS embedding               vector(1536),
  ADD COLUMN IF NOT EXISTS duplicate_of_article_id UUID REFERENCES raw_articles(id);

-- Índice parcial: o publish busca duplicados por canônico ao fechar linhagem
CREATE INDEX IF NOT EXISTS idx_raw_articles_duplicate_of
    ON raw_articles (duplicate_of_article_id)
    WHERE duplicate_of_article_id IS NOT NULL;

-- Sem índice ivfflat em raw_articles.embedding: a coluna é apenas
-- armazenamento para reúso pelo publish, nunca consultada por similaridade.
