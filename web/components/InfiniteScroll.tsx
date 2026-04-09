"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Event } from "@/lib/events";
import EventCard from "@/components/EventCard";

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
  const sentinelRef = useRef<HTMLDivElement>(null);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loading) return;
    setLoading(true);
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
      // silently fail — user can scroll back to retry
    } finally {
      setLoading(false);
    }
  }, [nextCursor, loading, category]);

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

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}

      <div ref={sentinelRef} className="py-4 text-center text-xs text-muted-foreground">
        {loading && "Carregando…"}
        {!loading && !nextCursor && events.length > 0 && "Fim do feed"}
      </div>
    </div>
  );
}
