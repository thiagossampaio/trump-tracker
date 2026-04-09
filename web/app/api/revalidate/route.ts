import { revalidateTag } from "next/cache";

export async function POST(request: Request) {
  const auth = request.headers.get("Authorization");
  if (!process.env.REVALIDATE_SECRET || auth !== `Bearer ${process.env.REVALIDATE_SECRET}`) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  revalidateTag("events-feed");
  return Response.json({ revalidated: true, timestamp: Date.now() });
}
