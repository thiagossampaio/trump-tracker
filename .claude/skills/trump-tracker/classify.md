# Skill: classify

Lê raw_articles com status='pending', chama Claude em batches de 5,
produz score + headline + summary, atualiza status no banco.

## Estratégias de economia de tokens

1. Filtro pré-IA no ingest reduz ~85% do volume
2. Truncagem do corpo: apenas 800 chars por artigo
3. Batching: 5 artigos por chamada (70% menos overhead de system prompt)
4. Prompt Caching da Anthropic: system prompt cacheado por 5 min
5. Resposta JSON direta sem markdown

## Roteamento por score

- score ≤ 3: UPDATE status='rejected'
- score 4–7: vai para dedup_agent
- score ≥ 8: vai para telegram_agent (moderação humana)
- confidence='low': sempre vai para moderação independente do score

## Custo estimado
~$0.002 por evento classificado = ~$1.20/mês (20 eventos/dia)