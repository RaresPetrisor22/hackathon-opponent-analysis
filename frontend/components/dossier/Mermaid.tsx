"use client";

import React, { useEffect, useRef } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  fontFamily: "'Inter', system-ui, sans-serif",
});

interface MermaidProps {
  chart: string;
}

export const Mermaid: React.FC<MermaidProps> = ({ chart }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      mermaid.render(`mermaid-${Math.random().toString(36).substring(2, 9)}`, chart).then(({ svg }) => {
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      }).catch((e) => {
        console.error("Mermaid parsing error:", e);
      });
    }
  }, [chart]);

  return <div ref={containerRef} className="mermaid-container" style={{ margin: "12px 0", textAlign: "center" }} />;
};
