"""
embedding_utils.py
------------------
Helpers compartilhados entre dedup_agent, publish_agent e scripts de
manutenção. Única fonte de verdade para:

  - construção do texto de embedding (elimina a divergência .strip()
    que existia entre dedup_agent e publish_agent)
  - geração de embedding com retry exponencial
  - normalização de headline para dedup lexical (syndication)
  - parse de colunas vector retornadas pelo PostgREST como string
  - similaridade de cosseno em memória
"""

import json
import logging
import re
import time

import numpy as np
from openai import OpenAI
from unidecode import unidecode

log = logging.getLogger("embedding_utils")

EMBEDDING_MODEL = "text-embedding-3-small"


def build_embedding_text(article: dict) -> str:
    """
    Texto canônico para embedding: headline_pt + summary_pt + category.
    Usado tanto pelo dedup (raw_articles) quanto por backfills de events
    (passar {"headline_pt": headline, "summary_pt": summary, ...}).
    """
    return " ".join(
        filter(
            None,
            [
                article.get("headline_pt"),
                article.get("summary_pt"),
                article.get("category"),
            ],
        )
    ).strip()


def generate_embedding(
    openai_client: OpenAI,
    text: str,
    retries: int = 3,
) -> list[float] | None:
    """
    Gera embedding de 1536 dimensões via text-embedding-3-small,
    com retry exponencial (1s, 2s, 4s). Retorna None se o texto for
    vazio ou se todas as tentativas falharem.
    """
    if not text or not text.strip():
        log.warning("Texto vazio — embedding não gerado")
        return None

    for attempt in range(retries):
        try:
            response = openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            if attempt < retries - 1:
                wait = 2**attempt
                log.warning(
                    f"OpenAI: erro ao gerar embedding (tentativa "
                    f"{attempt + 1}/{retries}, retry em {wait}s) — {e}"
                )
                time.sleep(wait)
            else:
                log.warning(f"OpenAI: embedding falhou após {retries} tentativas — {e}")
    return None


def normalize_headline(s: str | None) -> str:
    """
    Normaliza headline para comparação lexical exata:
    lowercase → remove acentos → remove pontuação → colapsa espaços.
    Pega a maioria dos casos de syndication (mesma matéria em N portais)
    sem custo de embedding.
    """
    if not s:
        return ""
    text = unidecode(s).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def parse_vector(value) -> list[float] | None:
    """
    Colunas vector chegam do PostgREST como string '[0.1,0.2,...]'.
    Aceita list (já parseado), str (json.loads) ou None.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else None
        except (ValueError, TypeError):
            return None
    return None


def cosine_sim(a, b) -> float:
    """
    Similaridade de cosseno. Embeddings da OpenAI são L2-normalizados,
    então cosseno = produto escalar — mas normalizamos por garantia.
    Aceita list ou np.ndarray.
    """
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)
