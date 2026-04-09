import { NextRequest, NextResponse } from "next/server";
import { unstable_cache } from "next/cache";
import { getSupabase } from "@/lib/supabase";
import { VALID_CATEGORIES } from "@/lib/events";

async function fetchEvents(
  cursor: string | null,
  category: string | null,
  limit: number
) {
  const supabase = getSupabase();
  let query = supabase
    .from("public_feed")
    .select(
      "id,slug,headline,summary,score,category,source_url,source_name,occurred_at,historical_context,tags,share_count,view_count",
      { count: "exact" }
    )
    .order("occurred_at", { ascending: false })
    .limit(limit + 1);

  if (cursor) query = query.lt("occurred_at", cursor);
  if (category && (VALID_CATEGORIES as readonly string[]).includes(category))
    query = query.eq("category", category);

  const { data, count, error } = await query;
  if (error) throw error;

  const hasMore = (data?.length ?? 0) > limit;
  const events = hasMore ? data!.slice(0, limit) : (data ?? []);
  const nextCursor = hasMore ? events[events.length - 1].occurred_at : null;

  return { events, nextCursor, total: count ?? 0 };
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const cursor = searchParams.get("cursor");
  const category = searchParams.get("category");
  const limit = Math.min(
    parseInt(searchParams.get("limit") ?? "20", 10),
    100
  );

  try {
    const cachedFetch = unstable_cache(
      () => fetchEvents(cursor, category, limit),
      ["events-feed", cursor ?? "start", category ?? "all", String(limit)],
      { tags: ["events-feed"], revalidate: 120 }
    );
    const result = await cachedFetch();
    return NextResponse.json(result);
  } catch (err) {
    console.error("Error fetching events:", err);
    return NextResponse.json(
      { error: "Failed to fetch events" },
      { status: 500 }
    );
  }
}
