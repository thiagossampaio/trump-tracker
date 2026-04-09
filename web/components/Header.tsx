import { unstable_cache } from "next/cache";
import { getSupabase } from "@/lib/supabase";

const getTotalCount = unstable_cache(
  async () => {
    try {
      const { count } = await getSupabase()
        .from("public_feed")
        .select("*", { count: "exact", head: true });
      return count ?? 0;
    } catch {
      return 0;
    }
  },
  ["events-total-count"],
  { tags: ["events-feed"], revalidate: 120 }
);

export default async function Header() {
  const total = await getTotalCount();
  const updatedAt = new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date());

  return (
    <header className="sticky top-0 z-20 border-b border-border/90 bg-background/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-end justify-between gap-3 px-4 py-4 sm:px-6">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Trump Tracker
          </p>
          <h1 className="text-base leading-tight font-semibold sm:text-lg">
            Feed de Aberrações
          </h1>
          <p className="text-xs text-muted-foreground">
            Arquivo factual em ordem cronológica reversa
          </p>
        </div>
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-right shadow-xs">
          <p className="text-2xl leading-none font-semibold tabular-nums text-primary">
            {total}
          </p>
          <p className="text-[11px] text-muted-foreground">eventos indexados</p>
          <p className="text-[11px] text-muted-foreground">atualizado em {updatedAt}</p>
        </div>
      </div>
    </header>
  );
}
