import { Fragment } from "react";
import type { Event } from "@/lib/events";
import EventCard from "@/components/EventCard";

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

/**
 * Feed de eventos renderizado no servidor, agrupado por data.
 * Substitui o antigo InfiniteScroll (client) — paginação convencional
 * via links facilita crawling e elimina o fetch client-side.
 */
export default function EventFeed({ events }: { events: Event[] }) {
  if (events.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card px-4 py-10 text-center">
        <p className="text-lg font-bold">Nenhum evento encontrado.</p>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Tente outro filtro ou volte para a primeira página.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
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
    </div>
  );
}
