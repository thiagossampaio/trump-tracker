"use client";

import { useState } from "react";
import { Share2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ShareButton({ title }: { title: string }) {
  const [state, setState] = useState<"idle" | "copied">("idle");

  async function handleShare() {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch {
        // user cancelled — do nothing
      }
    } else {
      await navigator.clipboard.writeText(url);
      setState("copied");
      setTimeout(() => setState("idle"), 2000);
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleShare}
      className="gap-2"
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
