import type { ScoreBreakdown as ScoreBreakdownType } from "@/lib/events";
import { getSeverity } from "@/lib/severity";
import { cn } from "@/lib/utils";

const DIMENSIONS: {
  key: keyof ScoreBreakdownType;
  label: string;
  desc: string;
  max: number;
}[] = [
  {
    key: "precedent",
    label: "Precedente histórico",
    desc: "Já aconteceu antes na história da república americana?",
    max: 4,
  },
  {
    key: "velocity",
    label: "Velocidade / escalada",
    desc: "Decisão abrupta, reversão ou escalada em 48h?",
    max: 2,
  },
  {
    key: "inst_impact",
    label: "Impacto institucional",
    desc: "Atinge normas não-escritas ou estruturas constitucionais?",
    max: 2,
  },
  {
    key: "system_reaction",
    label: "Reação do sistema",
    desc: "Judiciário, mercados, militares ou aliados reagiram?",
    max: 2,
  },
];

export default function ScoreBreakdown({
  breakdown,
}: {
  breakdown: ScoreBreakdownType | null;
}) {
  if (!breakdown) return null;

  const total = DIMENSIONS.reduce(
    (sum, { key }) => sum + (breakdown[key] ?? 0),
    0
  );
  const severity = getSeverity(total);

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
        Como o score foi calculado
      </h2>
      <div className="flex flex-col gap-5 rounded-xl border border-border bg-card p-5">
        {DIMENSIONS.map(({ key, label, desc, max }) => {
          const value = breakdown[key] ?? 0;
          return (
            <div key={key} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-semibold">{label}</span>
                <span
                  className={cn(
                    "text-sm font-bold tabular-nums",
                    value > 0 ? severity.text : "text-muted-foreground"
                  )}
                >
                  {value}/{max}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {desc}
              </p>
              {/* Células discretas — cada ponto da rubrica é um segmento */}
              <div className="mt-1 flex gap-1.5" aria-hidden>
                {Array.from({ length: max }).map((_, i) => (
                  <span
                    key={i}
                    className={cn(
                      "h-2 flex-1 rounded-full",
                      i < value
                        ? cn("bg-current", severity.text)
                        : "bg-muted"
                    )}
                  />
                ))}
              </div>
            </div>
          );
        })}

        <div className="flex items-center justify-between border-t border-border pt-4">
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">
            Total
          </span>
          <span className="flex items-baseline gap-2">
            <span
              className={cn("text-xl font-extrabold tabular-nums", severity.text)}
            >
              {total}/10
            </span>
            <span className={cn("text-xs font-semibold", severity.text)}>
              {severity.label}
            </span>
          </span>
        </div>
      </div>
    </section>
  );
}
