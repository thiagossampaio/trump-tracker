import Link from "next/link";
import Image from "next/image";
import { Globe } from "lucide-react";
import type { Event } from "@/lib/events";
import { getCategoryEmoji, getCategoryLabel } from "@/lib/events";
import { getSeverity } from "@/lib/severity";
import ShareButton from "@/components/ShareButton";
import { buildGoogleFaviconUrl, getSourceHost } from "@/lib/sources";
import { cn } from "@/lib/utils";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

export default function EventCard({ event }: { event: Event }) {
  const severity = getSeverity(event.score);
  const categoryLabel = getCategoryLabel(event.category);
  const categoryEmoji = getCategoryEmoji(event.category);
  const sourceHost = getSourceHost(event.source_url);
  const faviconUrl = buildGoogleFaviconUrl(event.source_url, 32);
  const isHighSeverity = event.score >= 8;

  return (
    <article
      className={cn(
        "group relative flex flex-col gap-2.5 rounded-xl border border-border bg-card p-5 shadow-xs transition-all duration-200 hover:-translate-y-px hover:border-primary/30 hover:shadow-md",
        isHighSeverity &&
          (event.score === 10
            ? "border-l-4 border-l-sev-critico"
            : "border-l-4 border-l-sev-alto")
      )}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {/* Chip de severidade — o score com significado */}
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-bold tabular-nums",
            severity.text,
            severity.bg,
            severity.border
          )}
        >
          {event.score}
          <span className="font-semibold">· {severity.label}</span>
        </span>
        <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-primary">
          <span aria-hidden>{categoryEmoji}</span>
          {categoryLabel}
        </span>
        <time
          className="ml-auto text-xs text-muted-foreground"
          dateTime={event.occurred_at}
        >
          {formatDate(event.occurred_at)}
        </time>
      </div>

      <h3 className="text-lg font-bold leading-snug tracking-tight sm:text-xl">
        <Link
          href={`/event/${event.slug}`}
          className="transition-colors group-hover:text-primary"
        >
          {/* Estende a área clicável ao card inteiro */}
          <span className="absolute inset-0" aria-hidden />
          {event.headline}
        </Link>
      </h3>

      <p className="line-clamp-2 font-serif text-[15px] leading-relaxed text-muted-foreground">
        {event.summary}
      </p>

      <div className="mt-1 flex items-center justify-between gap-2">
        <a
          href={event.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="relative z-10 inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground underline-offset-2 transition-colors hover:text-primary hover:underline"
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
          <span className="max-w-[12rem] truncate">
            {event.source_name || sourceHost || "Fonte primária"}
          </span>
        </a>
        <ShareButton
          compact
          title={event.headline}
          url={`/event/${event.slug}`}
          className="relative z-10"
        />
      </div>
    </article>
  );
}
