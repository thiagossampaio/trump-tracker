"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Event } from "@/lib/events";
import EventCard from "@/components/EventCard";
import { Button } from "@/components/ui/button";

type Props = {
  initialEvents: Event[];
  initialNextCursor: string | null;
  category: string | null;
};

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
        <div className="rounded-xl border border-border bg-card px-4 py-8 text-center">
          <p className="text-sm font-medium">Nenhum evento nesta categoria.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Tente outro filtro para ampliar o recorte.
          </p>
        </div>
      )}

      {events.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}

      <div
        ref={sentinelRef}
        className="py-4 text-center text-xs text-muted-foreground"
      >
        {loading && "Carregando…"}
        {!loading && hasError && nextCursor && (
          <div className="flex flex-col items-center gap-2">
            <p>Falha ao carregar mais eventos.</p>
            <Button variant="outline" size="sm" onClick={loadMore}>
              Tentar novamente
            </Button>
          </div>
        )}
        {!loading && !nextCursor && events.length > 0 && "Fim do feed"}
      </div>
    </div>
  );
}
