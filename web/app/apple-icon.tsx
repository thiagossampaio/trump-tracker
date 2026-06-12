import { ImageResponse } from "next/og";

export const runtime = "edge";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

const NAVY = "#0A3161";
const RED = "#B31942";

/** Apple touch icon — mesmo monograma do icon.tsx em 180px */
export default function AppleIcon() {
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
            fontSize: "96px",
            fontWeight: 800,
            letterSpacing: "-0.06em",
            fontFamily: "sans-serif",
          }}
        >
          TT
        </div>
        <div style={{ height: "16px", backgroundColor: RED, display: "flex" }} />
      </div>
    ),
    { ...size }
  );
}
