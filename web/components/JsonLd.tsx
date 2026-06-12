/**
 * Renderiza um bloco JSON-LD (schema.org) sanitizado.
 * Convenção do Next 16 (docs: 01-app/02-guides/json-ld.md): script com
 * dangerouslySetInnerHTML + escape de "<" para prevenir XSS.
 */
export default function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}
