# Skill: backfill

Preenche o feed com eventos históricos para o feed não começar vazio.

## Quando usar
- /tracker backfill [dias]
- /tracker backfill --from 2025-01-20 (desde a posse)
- Primeiro setup do sistema

## Estratégia por período

Curto (< 60 dias):
- ingest_agent com lookback_hours expandido
- NewsAPI (30 dias no free tier)
- GDELT (histórico ilimitado)

Médio (60–365 dias):
- GDELT como fonte primária
- Guardian API (histórico completo)
- Wikipedia API como âncora de eventos marcantes

Longo (> 1 ano, mandato 2017–2021):
- GDELT + Guardian + Wikipedia
- Processar em batches de 50/dia
- Dedup threshold mais conservador: 0.95

## Seed mínimo de eventos canônicos
Para o MVP, inserir manualmente os 5–10 eventos mais
marcantes da posse (jan/2025) com fontes primárias linkadas.