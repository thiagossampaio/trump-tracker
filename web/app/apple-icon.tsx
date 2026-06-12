import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

const NAVY = "#0A3161";
const RED = "#B31942";

/**
 * Apple touch icon — mesmo "Aberration Pulse" do icon.tsx em 180px.
 * Sem cantos arredondados no artwork: o iOS aplica a máscara.
 */
export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex" }}>
        <svg width="180" height="180" viewBox="0 0 100 100">
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
