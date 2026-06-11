import Link from "next/link";
import { VALID_CATEGORIES, getCategoryEmoji } from "@/lib/events";
import { cn } from "@/lib/utils";

/**
 * Filtro por categoria como links de navegação — funciona sem JavaScript
 * (requisito da SPEC-06) e produz URLs compartilháveis por filtro.
 */
export default function CategoryFilter({
  currentCategory,
}: {
  currentCategory: string | null;
}) {
  const tabs = [
    { label: "Todos", emoji: null as string | null, href: "/", active: currentCategory === null },
    ...VALID_CATEGORIES.map((cat) => ({
      label: cat,
      emoji: getCategoryEmoji(cat),
      href: `/?category=${encodeURIComponent(cat)}`,
      active: currentCategory === cat,
    })),
  ];

  return (
    <nav
      aria-label="Filtrar por categoria"
      className="no-scrollbar sticky top-[57px] z-20 -mx-4 flex gap-2 overflow-x-auto border-b border-border bg-background/95 px-4 py-2.5 backdrop-blur-sm sm:-mx-6 sm:px-6"
    >
      {tabs.map((tab) => (
        <Link
          key={tab.label}
          href={tab.href}
          scroll={false}
          aria-current={tab.active ? "page" : undefined}
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors",
            tab.active
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-primary"
          )}
        >
          {tab.emoji && <span aria-hidden>{tab.emoji}</span>}
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
