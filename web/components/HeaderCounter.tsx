"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Contador de aberrações do header. Oculto na home (pathname "/"), onde o
 * mesmo número já aparece como herói no hero — evita redundância.
 */
export default function HeaderCounter({
  formattedTotal,
}: {
  formattedTotal: string;
}) {
  const pathname = usePathname();
  if (pathname === "/") return null;

  return (
    <Link
      href="/"
      className="flex shrink-0 items-baseline gap-2 rounded-lg px-2 py-1 transition-colors hover:bg-muted"
    >
      <span className="text-2xl font-extrabold leading-none tracking-tight tabular-nums text-flag-red sm:text-3xl">
        {formattedTotal}
      </span>
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        aberrações
      </span>
    </Link>
  );
}
