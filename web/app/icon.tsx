import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";

const NAVY = "#0A3161";
const RED = "#B31942";

/**
 * Ícone do site — "Aberration Pulse": linha de base (norma histórica) com
 * pico anômalo, sobre Old Glory Blue e faixa ledger red (Civic Ledger).
 * Full-bleed: serve tanto para purpose "any" quanto "maskable" (pulso dentro
 * da zona segura central de 80%).
 */
export default function Icon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex" }}>
        <svg width="512" height="512" viewBox="0 0 100 100">
          <rect width="100" height="100" fill={NAVY} />
          <rect y="87" width="100" height="13" fill={RED} />
          <path
            d="M14 55H36L46 24L56 72L62 55H86"
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    { ...size }
  );
}
