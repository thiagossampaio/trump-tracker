import Link from "next/link";
import Image from "next/image";
import { Globe, Newspaper } from "lucide-react";
import type { Event } from "@/lib/events";
import { getCategoryLabel } from "@/lib/events";
import AberrationBadge from "@/components/AberrationBadge";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { buildGoogleFaviconUrl, getSourceHost } from "@/lib/sources";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

export default function EventCard({ event }: { event: Event }) {
  const categoryLabel = getCategoryLabel(event.category);
  const sourceHost = getSourceHost(event.source_url);
  const faviconUrl = buildGoogleFaviconUrl(event.source_url, 32);

  return (
    <article>
      <Card className="border border-border shadow-xs transition-shadow hover:shadow-md">
        <CardHeader className="gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <AberrationBadge score={event.score} />
            <Badge variant="secondary" className="font-medium">
              {categoryLabel}
            </Badge>
          </div>
          <CardTitle className="text-base leading-snug sm:text-lg">
            <Link href={`/event/${event.slug}`} className="hover:text-primary">
              {event.headline}
            </Link>
          </CardTitle>
          <CardDescription className="line-clamp-2 text-sm leading-relaxed">
            {event.summary}
          </CardDescription>
        </CardHeader>
        <CardContent className="pb-0" />
        <CardFooter className="relative z-10 flex items-center justify-between gap-2">
          <time className="text-xs text-muted-foreground" dateTime={event.occurred_at}>
            {formatDate(event.occurred_at)}
          </time>
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
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
            <span className="max-w-[11rem] truncate">
              {event.source_name || sourceHost || "Fonte primária"}
            </span>
            <Newspaper className="size-4" />
          </a>
        </CardFooter>
      </Card>
    </article>
  );
}
