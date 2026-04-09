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
