import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { ArrowLeft, Globe, Link2 } from "lucide-react";
import { getSupabase } from "@/lib/supabase";
import {
  getCategoryEmoji,
  getCategoryLabel,
  type EventDetail,
} from "@/lib/events";
import AberrationBadge from "@/components/AberrationBadge";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import ShareButton from "@/components/ShareButton";
import { Separator } from "@/components/ui/separator";
import { buildGoogleFaviconUrl, getSourceHost } from "@/lib/sources";

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

  const categoryLabel = getCategoryLabel(event.category);
  const categoryEmoji = getCategoryEmoji(event.category);
  const sourceHost = getSourceHost(event.source_url);
  const faviconUrl = buildGoogleFaviconUrl(event.source_url, 32);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6 sm:py-12">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-primary"
      >
        <ArrowLeft className="size-4" />
        Voltar ao arquivo
      </Link>

      <article className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2.5">
          <AberrationBadge score={event.score} showLabel />
          <span className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-primary">
            <span aria-hidden>{categoryEmoji}</span>
            {categoryLabel}
          </span>
        </div>

        <h1 className="text-3xl font-extrabold leading-tight tracking-tight sm:text-4xl">
          {event.headline}
        </h1>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
          <time dateTime={event.occurred_at}>{formatDate(event.occurred_at)}</time>
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-medium underline-offset-2 transition-colors hover:text-primary hover:underline"
          >
            {faviconUrl ? (
              <Image
                src={faviconUrl}
                alt=""
                width={16}
                height={16}
                className="size-4 rounded-sm"
              />
            ) : (
              <Globe className="size-4" />
            )}
            {event.source_name}
            <span className="text-xs text-muted-foreground/80">
              ({sourceHost ?? "origem"})
            </span>
          </a>
          {event.secondary_sources && event.secondary_sources.length > 0 && (
            <>
              {event.secondary_sources.map((src, i) => (
                <a
                  key={i}
                  href={src}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 underline-offset-2 transition-colors hover:text-primary hover:underline"
                >
                  <Link2 className="size-4" />
                  Fonte {i + 2}
                </a>
              ))}
            </>
          )}
        </div>

        <Separator />

        {/* Lede — o fato, em serifa para leitura confortável */}
        <p className="font-serif text-lg leading-relaxed text-foreground/90 sm:text-xl">
          {event.summary}
        </p>

        {event.historical_context && (
          <aside className="flex flex-col gap-2 rounded-r-xl border-l-4 border-l-primary bg-secondary/60 py-4 pl-5 pr-5">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
              Contexto histórico
            </p>
            <p className="font-serif text-[15px] leading-relaxed text-foreground/85">
              {event.historical_context}
            </p>
          </aside>
        )}

        <ScoreBreakdown breakdown={event.score_breakdown} />

        <div className="flex items-center justify-between gap-3 pt-1">
          <ShareButton title={event.headline} />
          <Link
            href="/"
            className="text-sm font-semibold text-muted-foreground transition-colors hover:text-primary"
          >
            ← arquivo completo
          </Link>
        </div>
      </article>
    </main>
  );
}
