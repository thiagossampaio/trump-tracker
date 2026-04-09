"use client";

import { useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VALID_CATEGORIES } from "@/lib/events";

const ALL_TABS = ["Todos", ...VALID_CATEGORIES] as const;

export default function CategoryFilter({
  currentCategory,
}: {
  currentCategory: string | null;
}) {
  const router = useRouter();
  const value = currentCategory ?? "Todos";

  function handleChange(cat: string) {
    if (cat === "Todos") {
      router.push("/", { scroll: false });
    } else {
      router.push(`/?category=${encodeURIComponent(cat)}`, { scroll: false });
    }
  }

  return (
    <Tabs value={value} onValueChange={handleChange} className="w-full">
      <TabsList className="h-auto w-full justify-start overflow-x-auto rounded-xl border border-border bg-card p-1">
        {ALL_TABS.map((cat) => (
          <TabsTrigger
            key={cat}
            value={cat}
            className="shrink-0 rounded-lg px-3 text-xs font-medium sm:text-sm"
          >
            {cat}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
