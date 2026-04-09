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
      router.push("/");
    } else {
      router.push(`/?category=${encodeURIComponent(cat)}`);
    }
  }

  return (
    <Tabs value={value} onValueChange={handleChange}>
      <TabsList className="h-auto w-full overflow-x-auto rounded-lg">
        {ALL_TABS.map((cat) => (
          <TabsTrigger key={cat} value={cat} className="shrink-0">
            {cat}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
