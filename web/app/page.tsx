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
    <main className="mx-auto max-w-2xl px-4 py-6 space-y-4">
      <CategoryFilter currentCategory={category} />
      <InfiniteScroll
        initialEvents={events}
        initialNextCursor={nextCursor}
        category={category}
      />
    </main>
  );
}
