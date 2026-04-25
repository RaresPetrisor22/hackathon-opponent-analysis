"use client";

import { Button } from "@/components/ui/button";

export function PrintButton() {
  return (
    <Button
      onClick={() => window.print()}
      variant="outline"
      className="no-print border-surface-2 text-muted-fg hover:text-white hover:border-muted text-xs font-mono"
    >
      Export PDF
    </Button>
  );
}
