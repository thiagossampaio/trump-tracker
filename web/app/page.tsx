import { unstable_cache } from "next/cache";
import { getSupabase } from "@/lib/supabase";
import { VALID_CATEGORIES, type Event } from "@/lib/events";
import { SEVERITY_LEGEND } from "@/lib/severity";
import CategoryFilter from "@/components/CategoryFilter";
import InfiniteScroll from "@/components/InfiniteScroll";
import { cn } from "@/lib/utils";

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

/** Estatísticas do hero: total, eventos críticos e início da janela de análise */
const getFeedStats = unstable_cache(
  async () => {
    try {
      const supabase = getSupabase();
      const [totalRes, criticalRes, firstRes] = await Promise.all([
        supabase.from("public_feed").select("*", { count: "exact", head: true }),
        supabase
          .from("public_feed")
          .select("*", { count: "exact", head: true })
          .gte("score", 8),
        supabase
          .from("public_feed")
          .select("occurred_at")
          .order("occurred_at", { ascending: true })
          .limit(1),
      ]);
      const since = firstRes.data?.[0]?.occurred_at ?? null;
      const daysTracking = since
        ? Math.max(
            1,
            Math.floor((Date.now() - new Date(since).getTime()) / 86_400_000)
          )
        : null;
      return {
        total: totalRes.count ?? 0,
        critical: criticalRes.count ?? 0,
        since,
        daysTracking,
      };
    } catch {
      return { total: 0, critical: 0, since: null, daysTracking: null };
    }
  },
  ["feed-stats"],
  { tags: ["events-feed"], revalidate: 120 }
);

function formatLongDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
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

  const [{ events, nextCursor }, stats] = await Promise.all([
    makeInitialFetcher(category)(),
    getFeedStats(),
  ]);

  const formattedTotal = new Intl.NumberFormat("pt-BR").format(stats.total);
  const daysTracking = stats.daysTracking;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-7 px-4 py-8 sm:px-6 sm:py-12">
      {/* Hero — o número é a evidência */}
      <section className="flex flex-col gap-5">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
          Monitoramento independente da presidência americana
        </p>

        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-2">
          <span className="text-7xl font-extrabold leading-none tracking-tighter tabular-nums text-flag-red sm:text-8xl">
            {formattedTotal}
          </span>
          <div className="flex flex-col gap-1">
            <p className="text-xl font-bold leading-tight sm:text-2xl">
              aberrações documentadas
            </p>
            {stats.since && (
              <p className="text-sm text-muted-foreground">
                desde {formatLongDate(stats.since)}
                {daysTracking && (
                  <>
                    {" "}
                    · <strong className="font-semibold text-foreground">
                      {daysTracking} dias
                    </strong>{" "}
                    de análise contínua
                  </>
                )}
              </p>
            )}
          </div>
        </div>

        <p className="max-w-2xl font-serif text-base leading-relaxed text-foreground/85 sm:text-lg">
          Eventos sem precedente histórico da presidência dos EUA, documentados
          com fonte verificável e classificados pelo{" "}
          <strong className="font-semibold">Aberration Score</strong> — uma
          medida de 1 a 10 do desvio em relação à norma histórica do cargo.
          {stats.critical > 0 && (
            <>
              {" "}
              <strong className="font-semibold text-sev-alto">
                {new Intl.NumberFormat("pt-BR").format(stats.critical)}
              </strong>{" "}
              deles não têm precedente nos últimos 50 anos.
            </>
          )}
        </p>

        {/* Legenda da escala — educa o leitor no primeiro contato */}
        <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-lg border border-border bg-card px-4 py-3">
          {SEVERITY_LEGEND.map(({ range, severity }) => (
            <span
              key={severity.key}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground"
            >
              <span
                className={cn("size-2 rounded-full bg-current", severity.text)}
                aria-hidden
              />
              <span className={cn("font-bold tabular-nums", severity.text)}>
                {range}
              </span>
              {severity.label}
            </span>
          ))}
        </div>
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
