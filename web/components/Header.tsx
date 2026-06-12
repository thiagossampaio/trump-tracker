import Link from "next/link";
import { unstable_cache } from "next/cache";
import { getSupabase } from "@/lib/supabase";
import HeaderCounter from "@/components/HeaderCounter";
import LogoMark from "@/components/Logo";

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
  const formattedTotal = new Intl.NumberFormat("pt-BR").format(total);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur-md">
      {/* Faixa institucional — Old Glory Blue / Old Glory Red */}
      <div
        className="h-[3px] w-full"
        style={{
          background:
            "linear-gradient(90deg, var(--primary) 0%, var(--primary) 62%, var(--flag-red) 62%, var(--flag-red) 100%)",
        }}
        aria-hidden
      />

      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="group flex min-w-0 items-center gap-2.5">
          <LogoMark className="size-9 shrink-0 transition-opacity group-hover:opacity-90 sm:size-10" />
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-lg font-extrabold leading-tight tracking-tight text-primary transition-opacity group-hover:opacity-80 sm:text-xl">
              Trump Tracker
            </span>
            <span className="hidden items-center gap-1.5 text-[11px] font-medium text-muted-foreground sm:flex">
              <span
                className="signal-pulse size-1.5 rounded-full bg-flag-red"
                aria-hidden
              />
              Monitoramento independente · fontes verificáveis
            </span>
          </span>
        </Link>

        <HeaderCounter formattedTotal={formattedTotal} />
      </div>
    </header>
  );
}
