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
    <section className="flex flex-col gap-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        Breakdown do Score
      </p>
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
        {DIMENSIONS.map(({ key, label, max }) => {
          const value = breakdown[key] ?? 0;
          const pct = max > 0 ? (value / max) * 100 : 0;
          return (
            <div key={key} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className="tabular-nums font-medium">
                  {value}/{max}
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-secondary">
                <div
                  className="h-2 rounded-full bg-primary transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
