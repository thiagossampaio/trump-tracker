import Link from "next/link";
import type { Event } from "@/lib/events";
import { CATEGORY_EMOJIS } from "@/lib/events";
import AberrationBadge from "@/components/AberrationBadge";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

export default function EventCard({ event }: { event: Event }) {
  const emoji = CATEGORY_EMOJIS[event.category] ?? "📌";

  return (
    <article className="group relative rounded-xl border border-border bg-card px-4 py-4 text-card-foreground ring-1 ring-foreground/5 transition-shadow hover:ring-foreground/15">
      <div className="flex flex-wrap items-center gap-2">
        <AberrationBadge score={event.score} />
        <span className="text-xs text-muted-foreground">
          {emoji} {event.category}
        </span>
      </div>

      <p className="mt-2 line-clamp-2 text-sm font-semibold leading-snug group-hover:text-primary">
        <Link
          href={`/event/${event.slug}`}
          className="after:absolute after:inset-0"
        >
          {event.headline}
        </Link>
      </p>

      <div className="relative z-10 mt-2 flex items-center gap-1 text-xs text-muted-foreground">
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
      </div>
    </article>
  );
}
