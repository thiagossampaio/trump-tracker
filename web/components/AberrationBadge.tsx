import { Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function scoreClassName(score: number): string {
  if (score <= 3)
    return "border-transparent bg-secondary text-secondary-foreground";
  if (score <= 5)
    return "border-transparent bg-amber-100 text-amber-900";
  if (score <= 7)
    return "border-transparent bg-orange-100 text-orange-900";
  if (score <= 9)
    return "border-transparent bg-destructive/15 text-destructive";
  return "border-transparent bg-red-200 text-red-950";
}

export default function AberrationBadge({ score }: { score: number }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 font-semibold tabular-nums tracking-tight",
        scoreClassName(score)
      )}
    >
      <Zap className="size-3!" />
      {score}/10
    </Badge>
  );
}
