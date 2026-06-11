import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { getSeverity } from "@/lib/severity";

export const runtime = "edge";

const NAVY = "#0A3161";
const RED = "#B31942";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const slug = searchParams.get("slug");

  if (!slug) {
    return new Response("Missing slug", { status: 400 });
  }

  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_KEY;
  if (!url || !key) {
    return new Response("Server misconfigured", { status: 500 });
  }

  const supabase = createClient(url, key);
  const { data: event } = await supabase
    .from("events")
    .select("headline,score,category")
    .eq("slug", slug)
    .is("merged_into_id", null)
    .single();

  if (!event) {
    return new Response("Not found", { status: 404 });
  }

  const severity = getSeverity(event.score);
  const color = severity.hex;

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
        {/* Topo: score + classificação da rubrica + categoria */}
        <div style={{ display: "flex", alignItems: "center", gap: "18px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              backgroundColor: `${color}14`,
              border: `2px solid ${color}55`,
              borderRadius: "999px",
              padding: "8px 20px",
              color: color,
              fontSize: "24px",
              fontWeight: 700,
            }}
          >
            {event.score}/10 · {severity.label}
          </div>
          <span
            style={{
              color: NAVY,
              fontSize: "20px",
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            {event.category}
          </span>
        </div>

        {/* Centro: headline */}
        <div
          style={{
            display: "flex",
            color: "#10243e",
            fontSize: "54px",
            fontWeight: 800,
            lineHeight: 1.12,
            letterSpacing: "-0.02em",
            maxWidth: "1020px",
            overflow: "hidden",
          }}
        >
          {event.headline.length > 120
            ? event.headline.slice(0, 120) + "…"
            : event.headline}
        </div>

        {/* Rodapé: branding */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span
            style={{
              color: RED,
              fontSize: "22px",
              fontWeight: 800,
              letterSpacing: "-0.01em",
            }}
          >
            Trump Tracker
          </span>
          <span style={{ color: "#5b6472", fontSize: "18px" }}>
            Arquivo de aberrações · fontes verificáveis
          </span>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      headers: {
        "Cache-Control": "public, max-age=86400, immutable",
      },
    }
  );
}
