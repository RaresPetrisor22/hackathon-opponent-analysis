import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Opponent Dossier — FC Universitatea Cluj",
  description: "Pre-match scouting intelligence for the coaching staff.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-white antialiased">
        <header className="border-b border-surface-2 px-6 py-3 flex items-center gap-3">
          <Link href="/" className="font-mono text-accent text-sm font-medium tracking-widest uppercase hover:text-accent-dim transition-colors">
            FC Universitatea Cluj
          </Link>
          <span className="text-muted-fg text-sm">/</span>
          <span className="text-muted-fg text-sm">Opponent Dossier</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
