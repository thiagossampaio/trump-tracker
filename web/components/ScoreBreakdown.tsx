import type { ScoreBreakdown as ScoreBreakdownType } from "@/lib/events";

const DIMENSIONS: {
  key: keyof ScoreBreakdownType;
  label: string;
  max: number;
}[] = [
  { key: "precedent", label: "Precedente histórico", max: 4 },
  { key: "velocity", label: "Velocidade", max: 2 },
  { key: "inst_impact", label: "Impacto institucional", max: 2 },
  { key: "system_reaction", label: "Reação do sistema", max: 2 },
];

export default function ScoreBreakdown({
  breakdown,
}: {
  breakdown: ScoreBreakdownType | null;
}) {
  if (!breakdown) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Breakdown do Score
      </p>
      <div className="space-y-2">
        {DIMENSIONS.map(({ key, label, max }) => {
          const value = breakdown[key] ?? 0;
          const pct = max > 0 ? (value / max) * 100 : 0;
          return (
            <div key={key}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className="tabular-nums font-medium">
                  {value}/{max}
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-secondary">
                <div
                  className="h-1.5 rounded-full bg-primary transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
