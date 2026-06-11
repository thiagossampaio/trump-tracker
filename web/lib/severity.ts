/**
 * Sistema de severidade do Aberration Score — fonte única de verdade.
 * Espelha a tabela de referência da rubrica oficial (briefing v0, §6.2):
 *   1–3 Normal presidencial · 4–5 Incomum · 6–7 Raro ·
 *   8–9 Sem precedente recente · 10 Sem precedente histórico
 * Cores calibradas para o tema claro "Civic Ledger".
 */

export type SeverityKey = "normal" | "incomum" | "raro" | "alto" | "critico";

export type Severity = {
  key: SeverityKey;
  /** Classificação oficial da rubrica */
  label: string;
  /** Classes Tailwind — literais para o scanner do TW4 */
  text: string;
  bg: string;
  border: string;
  /** Cor hex aproximada para contextos fora do Tailwind (OG image) */
  hex: string;
};

const SEVERITIES: Record<SeverityKey, Severity> = {
  normal: {
    key: "normal",
    label: "Normal presidencial",
    text: "text-sev-normal",
    bg: "bg-sev-normal/8",
    border: "border-sev-normal/25",
    hex: "#5b6472",
  },
  incomum: {
    key: "incomum",
    label: "Incomum",
    text: "text-sev-incomum",
    bg: "bg-sev-incomum/10",
    border: "border-sev-incomum/30",
    hex: "#a16207",
  },
  raro: {
    key: "raro",
    label: "Raro",
    text: "text-sev-raro",
    bg: "bg-sev-raro/10",
    border: "border-sev-raro/30",
    hex: "#c2410c",
  },
  alto: {
    key: "alto",
    label: "Sem precedente recente",
    text: "text-sev-alto",
    bg: "bg-sev-alto/10",
    border: "border-sev-alto/30",
    hex: "#b91c1c",
  },
  critico: {
    key: "critico",
    label: "Sem precedente histórico",
    text: "text-sev-critico",
    bg: "bg-sev-critico/10",
    border: "border-sev-critico/35",
    hex: "#7f1d1d",
  },
};

export function getSeverity(score: number): Severity {
  if (score <= 3) return SEVERITIES.normal;
  if (score <= 5) return SEVERITIES.incomum;
  if (score <= 7) return SEVERITIES.raro;
  if (score <= 9) return SEVERITIES.alto;
  return SEVERITIES.critico;
}

/** Legenda completa, em ordem crescente — usada na faixa educativa do feed */
export const SEVERITY_LEGEND: { range: string; severity: Severity }[] = [
  { range: "1–3", severity: SEVERITIES.normal },
  { range: "4–5", severity: SEVERITIES.incomum },
  { range: "6–7", severity: SEVERITIES.raro },
  { range: "8–9", severity: SEVERITIES.alto },
  { range: "10", severity: SEVERITIES.critico },
];
