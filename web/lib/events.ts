export type Event = {
  id: string;
  slug: string;
  headline: string;
  summary: string;
  score: number;
  category: string;
  source_url: string;
  source_name: string;
  occurred_at: string;
  historical_context: string | null;
  tags: string[];
  share_count: number;
  view_count: number;
};

export type ScoreBreakdown = {
  precedent: number;        // 0–4
  velocity: number;         // 0–2
  inst_impact: number;      // 0–2
  system_reaction: number;  // 0–2
};

/**
 * Fontes secundárias: o pipeline grava objetos {url, name, tier}, mas
 * registros antigos podem conter strings (URLs puras). Normalizar com
 * getSecondarySource() antes de renderizar.
 */
export type SecondarySource =
  | string
  | { url: string; name?: string; tier?: number };

export type EventDetail = Event & {
  score_breakdown: ScoreBreakdown | null;
  secondary_sources: SecondarySource[] | null;
};

export function getSecondarySource(src: SecondarySource): {
  url: string;
  name: string | null;
} {
  if (typeof src === "string") return { url: src, name: null };
  return { url: src.url, name: src.name?.trim() || null };
}

export const VALID_CATEGORIES = [
  "Institucional",
  "Econômico",
  "Diplomático",
  "Jurídico",
  "Militar",
  "Social",
  "Comunicação",
] as const;

export type Category = (typeof VALID_CATEGORIES)[number];

export const CATEGORY_LABELS: Record<string, string> = {
  Institucional: "Institucional",
  Econômico: "Econômico",
  Diplomático: "Diplomático",
  Jurídico: "Jurídico",
  Militar: "Militar",
  Social: "Social",
  Comunicação: "Comunicação",
};

// Emojis canônicos por categoria (briefing v0, §6.2 — _shared.md)
export const CATEGORY_EMOJI: Record<string, string> = {
  Institucional: "🏛️",
  Econômico: "📈",
  Diplomático: "🌐",
  Jurídico: "⚖️",
  Militar: "🎖️",
  Social: "👥",
  Comunicação: "📢",
};

export function getCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function getCategoryEmoji(category: string): string {
  return CATEGORY_EMOJI[category] ?? "📌";
}
