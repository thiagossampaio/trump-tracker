export function getSourceHost(sourceUrl: string): string | null {
  try {
    return new URL(sourceUrl).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export function getSourceOrigin(sourceUrl: string): string | null {
  try {
    return new URL(sourceUrl).origin;
  } catch {
    return null;
  }
}

export function buildGoogleFaviconUrl(
  sourceUrl: string,
  size = 32
): string | null {
  const origin = getSourceOrigin(sourceUrl);
  if (!origin) return null;

  const params = new URLSearchParams({
    client: "SOCIAL",
    type: "FAVICON",
    fallback_opts: "TYPE,SIZE,URL",
    url: origin,
    size: String(size),
  });

  return `https://t3.gstatic.com/faviconV2?${params.toString()}`;
}
