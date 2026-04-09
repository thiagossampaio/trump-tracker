# Skill: publish

Pega eventos aprovados (status='approved' ou 'approved_manual'),
gera embedding final, insere em events, revalida cache do Next.js.

## Fluxo
1. SELECT raw_articles WHERE status IN ('approved', 'approved_manual')
2. Gera embedding: text-embedding-3-small
3. Gera slug: {ação-kebab}-{YYYY-MM-DD}
4. INSERT events com ON CONFLICT DO NOTHING
5. UPDATE raw_articles SET status='published'
6. POST /api/revalidate para revalidar ISR do Next.js

## Revalidação Next.js no Cloudflare
POST /api/revalidate
Authorization: Bearer {REVALIDATE_SECRET}
Body: {"tags": ["events-feed"]}

## Regras
- NUNCA deletar um evento publicado — marcar como merged_into_id
- Score ≥ 8 só publica se review_status = 'human_approved' ou 'human_edited'
- ON CONFLICT DO NOTHING como proteção contra race conditions