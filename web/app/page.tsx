import type { Metadata } from "next";
import { unstable_cache } from "next/cache";
import { getSupabase } from "@/lib/supabase";
import { VALID_CATEGORIES, type Event } from "@/lib/events";
import { SEVERITY_LEGEND } from "@/lib/severity";
import { SITE_NAME } from "@/lib/site";
import CategoryFilter from "@/components/CategoryFilter";
import EventFeed from "@/components/EventFeed";
import Pagination from "@/components/Pagination";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

function parsePage(raw: string | undefined): number {
  const n = parseInt(raw ?? "1", 10);
  return Number.isFinite(n) && n >= 1 ? n : 1;
}

/** Frases por categoria para title/description únicos (evita duplicação com a home) */
const CATEGORY_PHRASES: Record<string, string> = {
  Institucional: "Aberrações institucionais",
  Econômico: "Aberrações econômicas",
  Diplomático: "Aberrações diplomáticas",
  Jurídico: "Aberrações jurídicas",
  Militar: "Aberrações militares",
  Social: "Aberrações sociais",
  Comunicação: "Aberrações de comunicação",
};

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; page?: string }>;
}): Promise<Metadata> {
  const { category: rawCat, page: rawPage } = await searchParams;
  const category =
    rawCat && (VALID_CATEGORIES as readonly string[]).includes(rawCat)
      ? rawCat
      : null;
  const page = parsePage(rawPage);
  const pageSuffix = page > 1 ? ` — página ${page}` : "";

  // Canonical preserva categoria e página (mesma forma dos links da paginação)
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (page > 1) params.set("page", String(page));
  const qs = params.toString();
  const canonical = qs ? `/?${qs}` : "/";

  // Home sem filtro: herda title/description do layout (com sufixo de página)
  if (!category) {
    return {
      ...(page > 1 && {
        title: `Arquivo de aberrações${pageSuffix} | ${SITE_NAME}`,
      }),
      alternates: { canonical },
    };
  }

  const phrase = CATEGORY_PHRASES[category] ?? `Aberrações — ${category}`;
  // O template "%s | Trump Tracker" do layout NÃO se aplica a page.tsx do
  // mesmo segmento (doc generate-metadata.md) — sufixo manual.
  const title = `${phrase} da presidência Trump${pageSuffix} | ${SITE_NAME}`;
  const description =
    `${phrase} sem precedente histórico da presidência americana, ` +
    `documentadas com fontes verificáveis e classificadas pelo Aberration Score.`;

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      description,
      url: canonical,
    },
    twitter: {
      title,
      description,
    },
  };
}

/**
 * Busca uma página do feed via offset (paginação convencional).
 * Numeração inteira na URL evita o bug de double-decode de timestamps
 * com "+" no OpenNext/Cloudflare (cursor "2026-…+00:00" virava espaço).
 */
function makePageFetcher(category: string | null, page: number) {
  return unstable_cache(
    async () => {
      try {
        const supabase = getSupabase();
        const from = (page - 1) * PAGE_SIZE;
        let query = supabase
          .from("public_feed")
          .select(
            "id,slug,headline,summary,score,category,source_url,source_name,occurred_at,historical_context,tags,share_count,view_count",
            { count: "exact" }
          )
          .order("occurred_at", { ascending: false })
          .range(from, from + PAGE_SIZE - 1);

        if (category) query = query.eq("category", category);

        const { data, count, error } = await query;
        if (error) throw error;

        return { events: (data ?? []) as Event[], total: count ?? 0 };
      } catch {
        // Inclui offset além do total (PostgREST 416) — página vazia
        return { events: [] as Event[], total: 0 };
      }
    },
    ["page-events", category ?? "all", String(page)],
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
  searchParams: Promise<{ category?: string; page?: string }>;
}) {
  const { category: rawCat, page: rawPage } = await searchParams;
  const category =
    rawCat && (VALID_CATEGORIES as readonly string[]).includes(rawCat)
      ? rawCat
      : null;
  const page = parsePage(rawPage);

  const [{ events, total }, stats] = await Promise.all([
    makePageFetcher(category, page)(),
    getFeedStats(),
  ]);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

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
            {/* h1 da página — número visível no span ao lado (aria-hidden seria
                redundante; o sr-only repete o total para leitores e crawlers) */}
            <h1 className="text-xl font-bold leading-tight tracking-normal sm:text-2xl">
              <span className="sr-only">{formattedTotal} </span>
              aberrações documentadas
              <span className="sr-only">
                {" "}
                — eventos sem precedente da presidência americana
                {category ? ` na categoria ${category}` : ""}
              </span>
            </h1>
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
      <EventFeed events={events} />
      <Pagination page={page} totalPages={totalPages} category={category} />
    </main>
  );
}
