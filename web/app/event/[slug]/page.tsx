import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import { getSupabase } from "@/lib/supabase";
import { CATEGORY_EMOJIS, type EventDetail } from "@/lib/events";
import AberrationBadge from "@/components/AberrationBadge";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import ShareButton from "@/components/ShareButton";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}

async function fetchEvent(slug: string): Promise<EventDetail | null> {
  const { data, error } = await getSupabase()
    .from("events")
    .select(
      "id,slug,headline,summary,score,score_breakdown,category,source_url,source_name,secondary_sources,occurred_at,historical_context,tags,share_count,view_count"
    )
    .eq("slug", slug)
    .is("merged_into_id", null)
    .single();

  if (error || !data) return null;
  return data as EventDetail;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const event = await fetchEvent(slug);
  if (!event) return {};

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "";

  return {
    title: event.headline,
    description: event.summary,
    openGraph: {
      title: event.headline,
      description: event.summary,
      images: [`${siteUrl}/api/og?slug=${slug}`],
    },
    twitter: {
      card: "summary_large_image",
      title: event.headline,
      description: event.summary,
      images: [`${siteUrl}/api/og?slug=${slug}`],
    },
  };
}

export default async function EventPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const event = await fetchEvent(slug);
  if (!event) notFound();

  const emoji = CATEGORY_EMOJIS[event.category] ?? "📌";

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 space-y-6">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        ← Voltar ao feed
      </Link>

      <article className="space-y-4">
        {/* Badge + categoria */}
        <div className="flex flex-wrap items-center gap-2">
          <AberrationBadge score={event.score} />
          <span className="text-xs text-muted-foreground">
            {emoji} {event.category}
          </span>
        </div>

        {/* Headline */}
        <h1 className="text-xl font-bold leading-snug">{event.headline}</h1>

        {/* Meta: data + fonte */}
        <div className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
          <time dateTime={event.occurred_at}>{formatDate(event.occurred_at)}</time>
          <span aria-hidden>·</span>
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline-offset-2 hover:underline"
          >
            {event.source_name}
          </a>
          {event.secondary_sources && event.secondary_sources.length > 0 && (
            <>
              <span aria-hidden>·</span>
              {event.secondary_sources.map((src, i) => (
                <a
                  key={i}
                  href={src}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline-offset-2 hover:underline"
                >
                  Fonte {i + 2}
                </a>
              ))}
            </>
          )}
        </div>

        <hr className="border-border" />

        {/* Summary */}
        <p className="text-sm leading-relaxed">{event.summary}</p>

        {/* Historical context */}
        {event.historical_context && (
          <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-foreground">
              Contexto histórico
            </p>
            {event.historical_context}
          </div>
        )}

        <hr className="border-border" />

        {/* Score breakdown */}
        <ScoreBreakdown breakdown={event.score_breakdown} />

        {/* Share */}
        <div className="pt-2">
          <ShareButton title={event.headline} />
        </div>
      </article>
    </main>
  );
}
