"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

const TARGET_ID = "dossier-content";
const BG = "#070b18";

export function PrintButton() {
  const [busy, setBusy] = useState(false);

  async function exportPdf() {
    if (busy) return;
    const node = document.getElementById(TARGET_ID);
    if (!node) return;

    setBusy(true);
    try {
      // Lazy-load to keep the initial bundle small.
      const [{ default: html2canvas }, jsPdfModule] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const { jsPDF } = jsPdfModule;

      const canvas = await html2canvas(node, {
        backgroundColor: BG,
        scale: 2,
        useCORS: true,
        logging: false,
        windowWidth: node.scrollWidth,
      });

      const pdf = new jsPDF({ unit: "pt", format: "a4", orientation: "portrait" });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      // Width-fit the rendered dossier to the PDF page; compute the slice
      // height in source-canvas pixels that corresponds to one PDF page.
      const ratio = pageWidth / canvas.width;
      const sliceHeightPx = Math.floor(pageHeight / ratio);

      const sliceCanvas = document.createElement("canvas");
      sliceCanvas.width = canvas.width;
      sliceCanvas.height = sliceHeightPx;
      const ctx = sliceCanvas.getContext("2d");
      if (!ctx) throw new Error("canvas 2d context unavailable");

      let y = 0;
      let first = true;
      while (y < canvas.height) {
        const remaining = canvas.height - y;
        const h = Math.min(sliceHeightPx, remaining);

        sliceCanvas.height = h;
        ctx.fillStyle = BG;
        ctx.fillRect(0, 0, sliceCanvas.width, h);
        ctx.drawImage(canvas, 0, y, canvas.width, h, 0, 0, canvas.width, h);

        const imgData = sliceCanvas.toDataURL("image/jpeg", 0.92);
        if (!first) pdf.addPage();
        pdf.addImage(imgData, "JPEG", 0, 0, pageWidth, h * ratio);

        first = false;
        y += sliceHeightPx;
      }

      pdf.save("dossier.pdf");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      onClick={exportPdf}
      disabled={busy}
      variant="outline"
      className="no-print border-surface-2 text-muted-fg hover:text-white hover:border-muted text-xs font-mono"
    >
      {busy ? "Exporting…" : "Export PDF"}
    </Button>
  );
}
