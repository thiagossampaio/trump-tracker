import { unstable_cache } from "next/cache";
import { getSupabase } from "@/lib/supabase";
import { VALID_CATEGORIES, type Event } from "@/lib/events";
import CategoryFilter from "@/components/CategoryFilter";
import InfiniteScroll from "@/components/InfiniteScroll";

function makeInitialFetcher(category: string | null) {
  return unstable_cache(
    async () => {
      try {
        const supabase = getSupabase();
        let query = supabase
          .from("public_feed")
          .select(
            "id,slug,headline,summary,score,category,source_url,source_name,occurred_at,historical_context,tags,share_count,view_count",
            { count: "exact" }
          )
          .order("occurred_at", { ascending: false })
          .limit(21);

        if (category) query = query.eq("category", category);

        const { data, count, error } = await query;
        if (error) throw error;

        const hasMore = (data?.length ?? 0) > 20;
        const events = (hasMore ? data!.slice(0, 20) : (data ?? [])) as Event[];
        const nextCursor = hasMore ? events[events.length - 1].occurred_at : null;

        return { events, nextCursor, total: count ?? 0 };
      } catch {
        return { events: [] as Event[], nextCursor: null, total: 0 };
      }
    },
    ["page-initial-events", category ?? "all"],
    { tags: ["events-feed"], revalidate: 120 }
  );
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const { category: rawCat } = await searchParams;
  const category =
    rawCat && (VALID_CATEGORIES as readonly string[]).includes(rawCat)
      ? rawCat
      : null;

  const { events, nextCursor } = await makeInitialFetcher(category)();

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <section className="rounded-xl border border-border bg-card px-4 py-4 shadow-xs sm:px-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          Data Journalism Feed
        </p>
        <h2 className="mt-2 text-xl leading-tight font-semibold sm:text-2xl">
          Eventos sem precedentes da política americana, com classificação factual.
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Cada item reúne fonte verificável, categoria editorial e Aberration
          Score para leitura rápida no mobile e contexto aprofundado no detalhe.
        </p>
      </section>

      <CategoryFilter currentCategory={category} />
      <InfiniteScroll
        key={category ?? "all"}
        initialEvents={events}
        initialNextCursor={nextCursor}
        category={category}
      />
    </main>
  );
}
