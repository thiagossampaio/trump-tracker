"use client";

import { useState } from "react";
import { Share2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  title: string;
  /** URL a compartilhar (relativa ou absoluta). Default: página atual. */
  url?: string;
  /** Variante compacta para uso dentro de cards do feed */
  compact?: boolean;
  className?: string;
};

export default function ShareButton({ title, url, compact = false, className }: Props) {
  const [state, setState] = useState<"idle" | "copied">("idle");

  async function handleShare() {
    const shareUrl = url
      ? new URL(url, window.location.origin).toString()
      : window.location.href;

    if (navigator.share) {
      try {
        await navigator.share({ title, url: shareUrl });
        return;
      } catch {
        // usuário cancelou — não faz nada
        return;
      }
    }

    await navigator.clipboard.writeText(shareUrl);
    setState("copied");
    setTimeout(() => setState("idle"), 2000);
  }

  if (compact) {
    return (
      <button
        type="button"
        onClick={handleShare}
        aria-label={state === "copied" ? "Link copiado" : "Compartilhar evento"}
        title="Compartilhar"
        className={cn(
          "inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          state === "copied" && "text-primary",
          className
        )}
      >
        {state === "copied" ? (
          <Check className="size-4" />
        ) : (
          <Share2 className="size-4" />
        )}
      </button>
    );
  }

  return (
    <Button
      variant="default"
      size="sm"
      onClick={handleShare}
      className={cn("gap-2 font-semibold", className)}
    >
      {state === "copied" ? (
        <>
          <Check className="size-4" />
          Link copiado!
        </>
      ) : (
        <>
          <Share2 className="size-4" />
          Compartilhar
        </>
      )}
    </Button>
  );
}
