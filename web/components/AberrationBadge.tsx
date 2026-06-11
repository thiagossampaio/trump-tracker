import { getSeverity } from "@/lib/severity";
import { cn } from "@/lib/utils";

type Props = {
  score: number;
  /** Exibe a classificação oficial da rubrica ao lado do número */
  showLabel?: boolean;
  className?: string;
};

export default function AberrationBadge({
  score,
  showLabel = false,
  className,
}: Props) {
  const severity = getSeverity(score);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-bold tabular-nums",
        severity.text,
        severity.bg,
        severity.border,
        className
      )}
    >
      {score}/10
      {showLabel && (
        <span className="font-semibold">· {severity.label}</span>
      )}
    </span>
  );
}
