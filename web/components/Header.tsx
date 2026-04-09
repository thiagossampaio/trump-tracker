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

  return (
    <header className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Trump Tracker
          </p>
          <h1 className="text-sm font-bold leading-tight">
            Feed de Aberrações
          </h1>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold tabular-nums leading-none">{total}</p>
          <p className="text-xs text-muted-foreground">desde a posse</p>
        </div>
      </div>
    </header>
  );
}
