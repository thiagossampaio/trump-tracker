import { Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function scoreClassName(score: number): string {
  if (score <= 3)
    return "bg-secondary text-secondary-foreground border-transparent";
  if (score <= 5)
    return "bg-yellow-500/20 text-yellow-700 border-yellow-500/30 dark:text-yellow-400";
  if (score <= 7)
    return "bg-orange-500/20 text-orange-700 border-orange-500/30 dark:text-orange-400";
  if (score <= 9)
    return "bg-destructive/10 text-destructive border-destructive/30";
  return "bg-red-900/20 text-red-900 border-red-900/30 dark:bg-red-900/40 dark:text-red-300";
}

export default function AberrationBadge({ score }: { score: number }) {
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 font-semibold tabular-nums", scoreClassName(score))}
    >
      <Zap className="size-3!" />
      {score}/10
    </Badge>
  );
}
