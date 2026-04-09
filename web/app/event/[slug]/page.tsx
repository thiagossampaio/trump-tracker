import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { ArrowLeft, Globe, Link2 } from "lucide-react";
import { getSupabase } from "@/lib/supabase";
import { getCategoryLabel, type EventDetail } from "@/lib/events";
import AberrationBadge from "@/components/AberrationBadge";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import ShareButton from "@/components/ShareButton";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  const sourceHost = getSourceHost(event.source_url);
  const faviconUrl = buildGoogleFaviconUrl(event.source_url, 32);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Voltar ao feed
      </Link>

      <article className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <AberrationBadge score={event.score} />
          <Badge variant="secondary">{categoryLabel}</Badge>
        </div>

        <h1 className="text-2xl leading-tight font-semibold sm:text-3xl">
          {event.headline}
        </h1>

        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <time dateTime={event.occurred_at}>{formatDate(event.occurred_at)}</time>
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 underline-offset-2 hover:text-foreground hover:underline"
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
            <span className="text-[11px] text-muted-foreground/90">
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
                  className="inline-flex items-center gap-1 underline-offset-2 hover:text-foreground hover:underline"
                >
                  <Link2 className="size-4" />
                  Fonte {i + 2}
                </a>
              ))}
            </>
          )}
        </div>

        <Separator />

        <p className="text-base leading-relaxed">{event.summary}</p>

        {event.historical_context && (
          <Card className="border border-border shadow-xs">
            <CardHeader>
              <CardTitle className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Contexto histórico
              </CardTitle>
              <CardDescription className="sr-only">
                Contexto comparativo com padrões presidenciais históricos
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0 text-sm leading-relaxed text-muted-foreground">
              {event.historical_context}
            </CardContent>
          </Card>
        )}

        <Separator />

        <ScoreBreakdown breakdown={event.score_breakdown} />

        <div className="pt-1">
          <ShareButton title={event.headline} />
        </div>
      </article>
    </main>
  );
}
