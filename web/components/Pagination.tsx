import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  page: number;
  totalPages: number;
  category: string | null;
};

/** Monta a URL da página preservando o filtro de categoria */
export function pageHref(page: number, category: string | null): string {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (page > 1) params.set("page", String(page));
  const qs = params.toString();
  return qs ? `/?${qs}` : "/";
}

/**
 * Janela de páginas: 1 … (atual−1) atual (atual+1) … última.
 * Retorna números e "…" como separador.
 */
function pageWindow(current: number, total: number): (number | "…")[] {
  const pages = new Set<number>([1, total, current - 1, current, current + 1]);
  const sorted = [...pages]
    .filter((p) => p >= 1 && p <= total)
    .sort((a, b) => a - b);

  const out: (number | "…")[] = [];
  let prev = 0;
  for (const p of sorted) {
    if (prev && p - prev > 1) out.push("…");
    out.push(p);
    prev = p;
  }
  return out;
}

const itemClass =
  "inline-flex h-9 min-w-9 items-center justify-center rounded-lg border px-2.5 text-sm font-semibold transition-colors";

/** Paginação convencional server-rendered — links reais, rastreáveis */
export default function Pagination({ page, totalPages, category }: Props) {
  if (totalPages <= 1) return null;

  return (
    <nav
      aria-label="Paginação do arquivo"
      className="flex flex-wrap items-center justify-center gap-1.5 pt-4"
    >
      {page > 1 ? (
        <Link
          href={pageHref(page - 1, category)}
          rel="prev"
          className={cn(
            itemClass,
            "border-border bg-card text-foreground hover:border-primary hover:text-primary"
          )}
        >
          <ChevronLeft className="size-4" />
          <span className="sr-only">Página anterior</span>
        </Link>
      ) : (
        <span className={cn(itemClass, "border-border/60 text-muted-foreground/50")}>
          <ChevronLeft className="size-4" />
        </span>
      )}

      {pageWindow(page, totalPages).map((p, i) =>
        p === "…" ? (
          <span
            key={`gap-${i}`}
            className="px-1.5 text-sm text-muted-foreground"
            aria-hidden
          >
            …
          </span>
        ) : p === page ? (
          <span
            key={p}
            aria-current="page"
            className={cn(itemClass, "border-primary bg-primary text-primary-foreground")}
          >
            {p}
          </span>
        ) : (
          <Link
            key={p}
            href={pageHref(p, category)}
            className={cn(
              itemClass,
              "border-border bg-card text-foreground hover:border-primary hover:text-primary"
            )}
          >
            {p}
          </Link>
        )
      )}

      {page < totalPages ? (
        <Link
          href={pageHref(page + 1, category)}
          rel="next"
          className={cn(
            itemClass,
            "border-border bg-card text-foreground hover:border-primary hover:text-primary"
          )}
        >
          <ChevronRight className="size-4" />
          <span className="sr-only">Próxima página</span>
        </Link>
      ) : (
        <span className={cn(itemClass, "border-border/60 text-muted-foreground/50")}>
          <ChevronRight className="size-4" />
        </span>
      )}
    </nav>
  );
}
