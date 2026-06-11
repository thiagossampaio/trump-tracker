"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import type { Event } from "@/lib/events";
import EventCard from "@/components/EventCard";
import { Button } from "@/components/ui/button";

type Props = {
  initialEvents: Event[];
  initialNextCursor: string | null;
  category: string | null;
};

/** Rótulo de grupo cronológico — também serve de chave de agrupamento */
function formatGroupDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}

function DateMarker({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-4 first:pt-0">
      <span className="text-xs font-bold uppercase tracking-wider text-primary">
        {label}
      </span>
      <span className="h-px flex-1 bg-border" aria-hidden />
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5">
      <div className="h-4 w-44 animate-pulse rounded-full bg-muted" />
      <div className="h-5 w-4/5 animate-pulse rounded bg-muted" />
      <div className="h-4 w-full animate-pulse rounded bg-muted/80" />
      <div className="h-3 w-36 animate-pulse rounded bg-muted/60" />
    </div>
  );
}

export default function InfiniteScroll({
  initialEvents,
  initialNextCursor,
  category,
}: Props) {
  const [events, setEvents] = useState<Event[]>(initialEvents);
  const [nextCursor, setNextCursor] = useState<string | null>(initialNextCursor);
  const [loading, setLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loading) return;
    setLoading(true);
    setHasError(false);
    try {
      const params = new URLSearchParams({ cursor: nextCursor, limit: "20" });
      if (category) params.set("category", category);
      const res = await fetch(`/api/events?${params}`);
      if (!res.ok) throw new Error("fetch failed");
      const data: { events: Event[]; nextCursor: string | null } =
        await res.json();
      setEvents((prev) => [...prev, ...data.events]);
      setNextCursor(data.nextCursor);
    } catch {
      setHasError(true);
    } finally {
      setLoading(false);
    }
  }, [nextCursor, loading, category]);

  useEffect(() => {
    setEvents(initialEvents);
    setNextCursor(initialNextCursor);
    setHasError(false);
  }, [category, initialEvents, initialNextCursor]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) loadMore();
      },
      { rootMargin: "200px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  const isEmpty = events.length === 0 && !loading && !nextCursor;

  return (
    <div className="flex flex-col gap-3">
      {isEmpty && (
        <div className="rounded-xl border border-border bg-card px-4 py-10 text-center">
          <p className="text-lg font-bold">Nenhum evento nesta categoria.</p>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Tente outro filtro para ampliar o recorte.
          </p>
        </div>
      )}

      {events.map((event, i) => {
        const groupLabel = formatGroupDate(event.occurred_at);
        const prevLabel =
          i > 0 ? formatGroupDate(events[i - 1].occurred_at) : null;
        const showMarker = groupLabel !== prevLabel;

        return (
          <Fragment key={event.id}>
            {showMarker && <DateMarker label={groupLabel} />}
            <div
              className="card-enter"
              style={{ animationDelay: `${(i % 20) * 35}ms` }}
            >
              <EventCard event={event} />
            </div>
          </Fragment>
        );
      })}

      {loading && (
        <>
          <CardSkeleton />
          <CardSkeleton />
        </>
      )}

      <div
        ref={sentinelRef}
        className="py-4 text-center text-xs text-muted-foreground"
      >
        {!loading && hasError && nextCursor && (
          <div className="flex flex-col items-center gap-2">
            <p>Falha ao carregar mais eventos.</p>
            <Button variant="outline" size="sm" onClick={loadMore}>
              Tentar novamente
            </Button>
          </div>
        )}
        {!loading && !nextCursor && events.length > 0 && (
          <span className="font-semibold uppercase tracking-[0.2em]">
            Fim do arquivo
          </span>
        )}
      </div>
    </div>
  );
}
