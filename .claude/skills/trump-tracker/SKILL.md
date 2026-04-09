---
name: trump-tracker
description: Pipeline de classificação de eventos aberrantes da presidência Trump. Triggers: /tracker ingest, /tracker classify, /tracker dedup, /tracker review, /tracker publish, /tracker backfill, /tracker status. Cola URL ou texto = auto-pipeline.
user-invocable: true
---

# Trump Tracker — Pipeline Autônomo

Assistente para o pipeline do Trump Tracker.
Leia o modo do comando e execute a ação correspondente.
Sempre leia [_shared.md](./_shared.md) primeiro — contém categorias,
rubrica do Aberration Score e padrões editoriais.

## Modos disponíveis

| Comando                    | Arquivo de contexto          |
|----------------------------|------------------------------|
| `/tracker ingest`          | [ingest.md](./ingest.md)     |
| `/tracker classify`        | [classify.md](./classify.md) |
| `/tracker dedup`           | [dedup.md](./dedup.md)       |
| `/tracker review`          | [review.md](./review.md)     |
| `/tracker publish`         | [publish.md](./publish.md)   |
| `/tracker backfill [dias]` | [backfill.md](./backfill.md) |
| `/tracker status`          | métricas direto do Supabase  |
| URL ou texto colado        | auto-pipeline (todos os modos em sequência) |

## Princípios editoriais

Este sistema classifica, não opina. O Aberration Score mede desvio
histórico da norma presidencial americana.

1. NUNCA publique sem pelo menos 1 fonte Tier 1 ou 2
2. SEMPRE link para a fonte primária
3. Human-in-the-loop OBRIGATÓRIO para score ≥ 8 via Telegram
4. Dedup obrigatório: mesmo evento = 1 card
