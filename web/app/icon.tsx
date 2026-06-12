import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";

const NAVY = "#0A3161";
const RED = "#B31942";

/** Ícone do site — monograma "TT" sobre Old Glory Blue com faixa red (Civic Ledger) */
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          backgroundColor: NAVY,
        }}
      >
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            fontSize: "280px",
            fontWeight: 800,
            letterSpacing: "-0.06em",
            fontFamily: "sans-serif",
          }}
        >
          TT
        </div>
        <div style={{ height: "48px", backgroundColor: RED, display: "flex" }} />
      </div>
    ),
    { ...size }
  );
}
