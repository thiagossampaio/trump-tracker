import { notFound, permanentRedirect } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { ArrowLeft, Globe, Link2 } from "lucide-react";
import { getSupabase } from "@/lib/supabase";
import {
  getCategoryEmoji,
  getCategoryLabel,
  getSecondarySource,
  type EventDetail,
} from "@/lib/events";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";
import AberrationBadge from "@/components/AberrationBadge";
import JsonLd from "@/components/JsonLd";
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

type EventRecord = EventDetail & {
  merged_into_id: string | null;
  updated_at: string | null;
};

async function fetchEvent(slug: string): Promise<EventRecord | null> {
  const { data, error } = await getSupabase()
    .from("events")
    .select(
      "id,slug,headline,summary,score,score_breakdown,category,source_url,source_name,secondary_sources,occurred_at,historical_context,tags,share_count,view_count,merged_into_id,updated_at"
    )
    .eq("slug", slug)
    .single();

  if (error || !data) return null;
  return data as EventRecord;
}

/**
 * Eventos mesclados (soft-merge de duplicatas) redirecionam 308 para o
 * canônico — preserva links já compartilhados em vez de 404.
 * Retorna o slug canônico ou null se não houver merge.
 */
async function resolveCanonicalSlug(event: EventRecord): Promise<string | null> {
  if (!event.merged_into_id) return null;
  const { data } = await getSupabase()
    .from("events")
    .select("slug")
    .eq("id", event.merged_into_id)
    .single();
  return data?.slug ?? null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const event = await fetchEvent(slug);
  // Inexistente ou mesclado: a página resolve (404 / redirect 308)
  if (!event || event.merged_into_id) return {};

  const ogImage = `${SITE_URL}/api/og?slug=${slug}`;
  const canonical = `/event/${slug}`;

  return {
    title: event.headline,
    description: event.summary,
    alternates: { canonical },
    openGraph: {
      type: "article",
      title: event.headline,
      description: event.summary,
      url: canonical,
      publishedTime: event.occurred_at,
      modifiedTime: event.updated_at ?? undefined,
      section: getCategoryLabel(event.category),
      images: [{ url: ogImage, width: 1200, height: 630, alt: event.headline }],
    },
    twitter: {
      card: "summary_large_image",
      title: event.headline,
      description: event.summary,
      images: [ogImage],
    },
  };
}

/** JSON-LD NewsArticle (schema.org) do evento */
function buildEventJsonLd(event: EventRecord) {
  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: event.headline,
    description: event.summary,
    datePublished: event.occurred_at,
    dateModified: event.updated_at ?? event.occurred_at,
    inLanguage: "pt-BR",
    articleSection: getCategoryLabel(event.category),
    image: [`${SITE_URL}/api/og?slug=${event.slug}`],
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${SITE_URL}/event/${event.slug}`,
    },
    isBasedOn: event.source_url,
    publisher: {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: SITE_NAME,
      url: SITE_URL,
      logo: { "@type": "ImageObject", url: `${SITE_URL}/icon` },
      description: SITE_DESCRIPTION,
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

  // Duplicata mesclada → 308 para o evento canônico (preserva links compartilhados)
  if (event.merged_into_id) {
    const canonicalSlug = await resolveCanonicalSlug(event);
    if (canonicalSlug) permanentRedirect(`/event/${canonicalSlug}`);
    notFound();
  }

  const categoryLabel = getCategoryLabel(event.category);
  const categoryEmoji = getCategoryEmoji(event.category);
  const sourceHost = getSourceHost(event.source_url);
  const faviconUrl = buildGoogleFaviconUrl(event.source_url, 32);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6 sm:py-12">
      <JsonLd data={buildEventJsonLd(event)} />
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
              {event.secondary_sources.map((src, i) => {
                const { url, name } = getSecondarySource(src);
                if (!url) return null;
                return (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 underline-offset-2 transition-colors hover:text-primary hover:underline"
                  >
                    <Link2 className="size-4" />
                    {name ?? `Fonte ${i + 2}`}
                  </a>
                );
              })}
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
