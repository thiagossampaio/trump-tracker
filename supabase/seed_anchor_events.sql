-- ──────────────────────────────────────────────────────────────────────────────
-- Eventos âncora — Posse de Trump (20 jan 2025)
-- ──────────────────────────────────────────────────────────────────────────────
-- Esses eventos servem como calibração de score para o classify_agent.
-- Representam o espectro de aberração: de 1 (esperado) a 9 (sem precedente histórico).
--
-- Executar no Supabase SQL Editor.
-- ON CONFLICT DO NOTHING torna idempotente (pode ser reaplicado sem duplicatas).
-- ──────────────────────────────────────────────────────────────────────────────

INSERT INTO events (
    slug, headline, summary, historical_context,
    score, score_breakdown, category, confidence,
    source_url, source_name, source_tier,
    occurred_at, review_status, tags
) VALUES

-- Evento 1: Posse — score 1 (esperado, sem aberração)
(
    'trump-sworn-in-47th-president-2025-01-20',
    'Trump toma posse como 47º Presidente dos Estados Unidos',
    'Donald Trump foi empossado como o 47º Presidente dos Estados Unidos em cerimônia realizada no Capitólio em Washington D.C., tornando-se o segundo presidente na história americana a servir mandatos não consecutivos.',
    'Grover Cleveland foi o único presidente a servir mandatos não consecutivos (1885–1889 e 1893–1897). A posse de Trump replica esse precedente histórico, tornando o evento esperado dentro das normas institucionais.',
    1,
    '{"precedent": 1, "velocity": 0, "inst_impact": 0, "system_reaction": 0}',
    'Institucional',
    'high',
    'https://apnews.com/article/trump-inauguration-president-2025',
    'AP News',
    1,
    '2025-01-20T17:00:00+00:00',
    'human_approved',
    '["posse", "inauguração", "47th president"]'
),

-- Evento 2: Perdão em massa dos réus de 6 de janeiro — score 9
(
    'trump-pardons-jan6-rioters-2025-01-20',
    'Trump concede perdão em massa a mais de 1.500 condenados pelo ataque ao Capitólio de 6 de janeiro',
    'Na primeira hora de seu mandato, Trump assinou ordem executiva concedendo perdão presidencial a aproximadamente 1.500 pessoas condenadas por crimes relacionados ao ataque ao Capitólio em 6 de janeiro de 2021, incluindo indivíduos condenados por violência contra policiais.',
    'Nenhum presidente americano havia concedido perdão em massa a participantes de um ataque à sede do poder legislativo. O perdão de membros violentos de uma multidão que tentou interromper a certificação eleitoral não tem precedente na história presidencial americana.',
    9,
    '{"precedent": 4, "velocity": 2, "inst_impact": 2, "system_reaction": 1}',
    'Jurídico',
    'high',
    'https://apnews.com/article/trump-pardon-january-6-capitol-riot-2025',
    'AP News',
    1,
    '2025-01-20T18:30:00+00:00',
    'human_approved',
    '["perdão", "6 de janeiro", "Capitólio", "executive order"]'
),

-- Evento 3: Retirada do Acordo de Paris — score 7
(
    'trump-withdraws-paris-climate-agreement-2025-01-20',
    'Trump retira os EUA do Acordo de Paris sobre mudanças climáticas pela segunda vez',
    'Trump assinou decreto retirando os Estados Unidos do Acordo de Paris sobre mudanças climáticas, repetindo ação tomada em seu primeiro mandato. A retirada é imediata como intenção formal e se completa em 12 meses conforme o tratado.',
    'Os EUA já haviam saído do Acordo de Paris no primeiro mandato Trump (2017) e retornado sob Biden (2021). A segunda saída estabelece um padrão de instabilidade diplomática climática sem precedente para uma potência do G7.',
    7,
    '{"precedent": 3, "velocity": 1, "inst_impact": 2, "system_reaction": 1}',
    'Diplomático',
    'high',
    'https://apnews.com/article/trump-paris-agreement-climate-withdrawal-2025',
    'AP News',
    1,
    '2025-01-20T19:00:00+00:00',
    'human_approved',
    '["Paris", "clima", "acordo internacional", "executive order"]'
),

-- Evento 4: Retirada da OMS — score 8
(
    'trump-withdraws-who-2025-01-20',
    'Trump retira os EUA da Organização Mundial da Saúde',
    'Trump assinou decreto retirando os Estados Unidos da Organização Mundial da Saúde (OMS), efetivando a saída americana da principal agência de saúde global da ONU. A saída tem impacto imediato no financiamento e na participação americana em emergências sanitárias globais.',
    'A segunda retirada da OMS em um mandato presidencial americano, após a tentativa incompleta de 2020, estabelece um padrão de isolacionismo sanitário global sem precedente. Os EUA são o maior contribuinte individual da OMS.',
    8,
    '{"precedent": 3, "velocity": 2, "inst_impact": 2, "system_reaction": 1}',
    'Diplomático',
    'high',
    'https://apnews.com/article/trump-who-withdrawal-world-health-organization-2025',
    'AP News',
    1,
    '2025-01-20T19:30:00+00:00',
    'human_approved',
    '["OMS", "WHO", "saúde global", "executive order"]'
),

-- Evento 5: Ordem executiva contestando o jus soli — score 9
(
    'trump-birthright-citizenship-executive-order-2025-01-20',
    'Trump assina ordem executiva tentando acabar com a cidadania por nascimento para filhos de imigrantes ilegais',
    'Trump assinou ordem executiva determinando que filhos de imigrantes ilegais e de visitantes temporários nascidos em território americano não teriam direito automático à cidadania americana — uma interpretação que contraria diretamente o texto da 14ª Emenda da Constituição.',
    'A 14ª Emenda (1868) garante cidadania a toda pessoa nascida nos EUA. Nenhum presidente havia tentado revogar o jus soli por decreto executivo. A medida foi imediatamente bloqueada por tribunais federais por ser considerada inconstitucional.',
    9,
    '{"precedent": 4, "velocity": 2, "inst_impact": 2, "system_reaction": 1}',
    'Jurídico',
    'high',
    'https://apnews.com/article/trump-birthright-citizenship-14th-amendment-executive-order-2025',
    'AP News',
    1,
    '2025-01-20T20:00:00+00:00',
    'human_approved',
    '["cidadania", "14ª Emenda", "imigrações", "jus soli", "executive order"]'
)

ON CONFLICT (slug) DO NOTHING;
