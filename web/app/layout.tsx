import type { Metadata } from "next";
import { Libre_Franklin, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";

const franklin = Libre_Franklin({
  variable: "--font-franklin",
  subsets: ["latin"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Trump Tracker — Arquivo de Aberrações",
    template: "%s | Trump Tracker",
  },
  description:
    "Monitoramento independente que documenta e classifica eventos sem precedente histórico da presidência americana, com fontes verificáveis.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${franklin.variable} ${sourceSerif.variable} h-full antialiased`}
    >
      <body className="flex min-h-svh flex-col bg-background text-foreground">
        <Header />
        <div className="mx-auto w-full max-w-6xl flex-1">{children}</div>
        <footer className="mt-16 border-t border-border bg-muted/50">
          <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-4 py-10 sm:px-6">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
              Trump Tracker
            </p>
            <p className="max-w-2xl font-serif text-base leading-relaxed text-foreground/85">
              Arquivo factual e independente. O Aberration Score mede o desvio
              da norma histórica da presidência americana — não aprovação
              política.
            </p>
            <div className="flex flex-col gap-1.5 text-xs leading-relaxed text-muted-foreground">
              <p>
                Score = precedente histórico (0–4) + velocidade (0–2) + impacto
                institucional (0–2) + reação do sistema (0–2)
              </p>
              <p>
                Fontes Tier 1–2 verificáveis · classificação automatizada ·
                revisão humana obrigatória para score ≥ 8
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
