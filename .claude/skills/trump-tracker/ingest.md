# Skill: ingest

Busca eventos nas fontes configuradas, normaliza o formato e persiste
na tabela raw_articles com status='pending'.

## Quando usar
- /tracker ingest
- Chamado pelo GitHub Actions a cada 2h

## O que fazer

1. Ler config/sources.yml (queries, fontes ativas, lookback_hours)
2. Buscar em paralelo: NewsAPI, GDELT, Guardian, AP RSS, Reuters RSS
3. Filtro pré-IA por keyword no título
4. Dedup por URL em batch contra raw_articles
5. INSERT com status='pending', priority baseada em HIGH_PRIORITY_TERMS
6. Imprimir relatório

## Filtros de relevância (sem IA)

RELEVANCE_TERMS = ["trump", "white house", "executive order",
                   "president trump", "trump administration"]

HIGH_PRIORITY_TERMS = ["unprecedented", "first time", "fires",
                       "fired", "emergency", "pardon", "reversed",
                       "invokes", "suspended", "never before"]

## Relatório final
Fontes consultadas, artigos brutos, após filtro, dedup, inseridos.
Próximo passo: classify_agent.py
