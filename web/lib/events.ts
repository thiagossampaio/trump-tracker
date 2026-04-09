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

export type EventDetail = Event & {
  score_breakdown: ScoreBreakdown | null;
  secondary_sources: string[] | null;
};

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

export const CATEGORY_EMOJIS: Record<string, string> = {
  Institucional: "🏛️",
  Econômico: "💰",
  Diplomático: "🤝",
  Jurídico: "⚖️",
  Militar: "🎖️",
  Social: "👥",
  Comunicação: "📢",
};
