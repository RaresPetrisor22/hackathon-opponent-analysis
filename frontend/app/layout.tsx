import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "U-PPONENT ARCHIVE — FC Universitatea Cluj",
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
        <header className="border-b border-surface-2 bg-surface/50 backdrop-blur-md px-6 py-3.5 flex items-center gap-4 relative z-10">
          <span className="size-2 rounded-full bg-accent shadow-[0_0_10px_rgba(96,165,250,0.7)]" aria-hidden />
          <Link
            href="/"
            className="font-bold text-white text-sm tracking-[0.18em] uppercase hover:text-accent transition-colors"
          >
            FC Universitatea Cluj
          </Link>
          <span className="h-4 w-px bg-surface-2" aria-hidden />
          <span className="font-mono text-muted-fg text-xs tracking-[0.22em] uppercase">
            U-PPONENT ARCHIVE
          </span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
