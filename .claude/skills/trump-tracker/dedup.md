# Skill: dedup

Detecta eventos duplicados usando pgvector + matching de data/categoria.

## Embedding
- Modelo: text-embedding-3-small (1536 dims)
- Texto: "{headline} {summary} {category}"

## Tabela de decisão por cosine similarity

| Similaridade | Ação                                      |
|--------------|-------------------------------------------|
| ≥ 0.92       | Duplicata exata → descartar               |
| 0.80–0.91    | Mesmo episódio → verificar se é update    |
| 0.65–0.79    | Relacionado → publicar separado, linkar   |
| < 0.65       | Independente → publicar normalmente       |

## Update vs. Duplicata (similaridade 0.80–0.91)

É UPDATE se:
- occurred_at do novo > existente em mais de 2h
- Adiciona informação nova (keywords: blocks, responds, reverses)

É DUPLICATA se:
- occurred_at dentro de 4h do existente
- Não adiciona informação nova
