import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";

export const runtime = "edge";

function scoreColor(score: number): string {
  if (score <= 3) return "#6b7280";
  if (score <= 5) return "#ca8a04";
  if (score <= 7) return "#ea580c";
  if (score <= 9) return "#dc2626";
  return "#7f1d1d";
}

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

  const color = scoreColor(event.score);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#09090b",
          padding: "60px 64px",
          fontFamily: "sans-serif",
        }}
      >
        {/* Top: score badge + category */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              backgroundColor: `${color}22`,
              border: `1.5px solid ${color}55`,
              borderRadius: "8px",
              padding: "6px 14px",
              color: color,
              fontSize: "20px",
              fontWeight: 700,
            }}
          >
            ⚡ {event.score}/10
          </div>
          <span style={{ color: "#71717a", fontSize: "18px" }}>
            {event.category}
          </span>
        </div>

        {/* Center: headline */}
        <div
          style={{
            display: "flex",
            color: "#fafafa",
            fontSize: "52px",
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            maxWidth: "1000px",
            overflow: "hidden",
          }}
        >
          {event.headline.length > 120
            ? event.headline.slice(0, 120) + "…"
            : event.headline}
        </div>

        {/* Bottom: branding */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span
            style={{
              color: "#52525b",
              fontSize: "18px",
              fontWeight: 600,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}
          >
            Trump Tracker
          </span>
          <span style={{ color: "#27272a", fontSize: "18px" }}>·</span>
          <span style={{ color: "#52525b", fontSize: "18px" }}>
            Feed de Aberrações
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
