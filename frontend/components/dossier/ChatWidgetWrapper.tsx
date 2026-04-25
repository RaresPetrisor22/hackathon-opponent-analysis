"use client";

import { ChatWidget } from "@/components/dossier/ChatWidget";

/**
 * Thin client-side wrapper so we can render the chat widget
 * from within a Server Component page (dossier/[teamId]/page.tsx).
 */
export function ChatWidgetWrapper({ dossier }: { dossier: Record<string, unknown> }) {
  return <ChatWidget dossier={dossier} />;
}
