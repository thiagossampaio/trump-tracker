import type { MetadataRoute } from "next";
import { getSupabase } from "@/lib/supabase";
import { VALID_CATEGORIES } from "@/lib/events";
import { SITE_URL } from "@/lib/site";

// Regenera o sitemap no máximo a cada hora
export const revalidate = 3600;

const PAGE_SIZE = 1000; // limite do PostgREST por request

type EventRow = {
  slug: string;
  occurred_at: string;
  updated_at: string | null;
};

/** Todos os eventos ativos (merged_into_id IS NULL), paginado */
async function fetchAllActiveEvents(): Promise<EventRow[]> {
  const supabase = getSupabase();
  const rows: EventRow[] = [];
  let offset = 0;
  while (true) {
    const { data, error } = await supabase
      .from("events")
      .select("slug, occurred_at, updated_at")
      .is("merged_into_id", null)
      .order("occurred_at", { ascending: false })
      .range(offset, offset + PAGE_SIZE - 1);
    if (error) throw error;
    rows.push(...((data ?? []) as EventRow[]));
    if (!data || data.length < PAGE_SIZE) break;
    offset += PAGE_SIZE;
  }
  return rows;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  let events: EventRow[] = [];
  try {
    events = await fetchAllActiveEvents();
  } catch {
    // Banco indisponível: ainda servimos home + categorias
  }

  const home: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: "hourly",
      priority: 1.0,
    },
  ];

  const categories: MetadataRoute.Sitemap = VALID_CATEGORIES.map((cat) => ({
    url: `${SITE_URL}/?category=${encodeURIComponent(cat)}`,
    lastModified: new Date(),
    changeFrequency: "daily",
    priority: 0.6,
  }));

  const eventUrls: MetadataRoute.Sitemap = events.map((e) => ({
    url: `${SITE_URL}/event/${e.slug}`,
    lastModified: new Date(e.updated_at ?? e.occurred_at),
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  return [...home, ...categories, ...eventUrls];
}
