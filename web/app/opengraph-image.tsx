import { ImageResponse } from "next/og";

export const alt =
  "Trump Tracker — Arquivo de aberrações da presidência americana, com fontes verificáveis";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const NAVY = "#0A3161";
const RED = "#B31942";

/**
 * OG image default da home — mesma linguagem visual do /api/og (eventos):
 * papel branco, faixa navy no topo, faixa red na base, branding central.
 * Estática de propósito (sem contador) para não ficar obsoleta em caches.
 */
export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#ffffff",
          padding: "56px 64px",
          fontFamily: "sans-serif",
          borderTop: `8px solid ${NAVY}`,
          borderBottom: `8px solid ${RED}`,
        }}
      >
        <div
          style={{
            display: "flex",
            color: NAVY,
            fontSize: "20px",
            fontWeight: 700,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          Monitoramento independente da presidência americana
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          <div
            style={{
              display: "flex",
              color: RED,
              fontSize: "92px",
              fontWeight: 800,
              letterSpacing: "-0.03em",
              lineHeight: 1,
            }}
          >
            Trump Tracker
          </div>
          <div
            style={{
              display: "flex",
              color: "#10243e",
              fontSize: "34px",
              fontWeight: 600,
              lineHeight: 1.25,
              maxWidth: "980px",
            }}
          >
            Arquivo factual de eventos sem precedente histórico, classificados
            pelo Aberration Score
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ color: NAVY, fontSize: "22px", fontWeight: 700 }}>
            stalkers.ai
          </span>
          <span style={{ color: "#5b6472", fontSize: "18px" }}>
            Arquivo de aberrações · fontes verificáveis
          </span>
        </div>
      </div>
    ),
    { ...size }
  );
}
