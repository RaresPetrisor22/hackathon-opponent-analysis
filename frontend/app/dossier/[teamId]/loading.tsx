import type { ReactNode } from "react";

function Bone({ className }: { className?: string }) {
  return (
    <div className={`bg-surface-2 animate-pulse rounded ${className ?? ""}`} />
  );
}

function PanelSkeleton({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded border border-surface-2 bg-surface p-5 space-y-4 ${className ?? ""}`}>
      {children}
    </div>
  );
}

export default function DossierLoading() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">

      {/* Page header */}
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <Bone className="h-3 w-52 animate-pulse" />
          <Bone className="h-9 w-64 animate-pulse" />
          <Bone className="h-3 w-40 animate-pulse" />
        </div>
      </div>

      {/* Hero — Matchup Intelligence */}
      <div
        className="rounded-lg border border-accent/10 bg-surface p-6 space-y-5"
        style={{ boxShadow: "0 0 56px rgba(0, 255, 136, 0.03)" }}
      >
        {/* Header row */}
        <div className="flex items-center gap-3">
          <Bone className="h-5 w-24 animate-pulse" />
          <Bone className="h-5 w-48 animate-pulse" />
        </div>

        {/* Hero grid: winning condition + radar */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Winning condition — 3 cols */}
          <div className="lg:col-span-3 rounded border border-surface-2 bg-surface-2/20 p-6 space-y-5 animate-pulse">
            <Bone className="h-3 w-36" />
            <div className="flex items-start gap-6">
              <div className="space-y-2 shrink-0">
                <Bone className="h-20 w-32" />
                <Bone className="h-3 w-28" />
              </div>
              <div className="w-px self-stretch bg-surface-2" />
              <div className="flex-1 space-y-2.5">
                <Bone className="h-3 w-20" />
                <Bone className="h-7 w-48" />
                <Bone className="h-3 w-40" />
                <Bone className="h-5 w-28" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Bone className="h-1.5 w-full" />
              <Bone className="h-3 w-48" />
            </div>
          </div>

          {/* Radar — 2 cols */}
          <div className="lg:col-span-2 rounded border border-surface-2 bg-surface-2/20 p-4 flex flex-col gap-2 animate-pulse">
            <Bone className="h-3 w-32" />
            <Bone className="h-3 w-44" />
            <div className="flex-1 flex items-center justify-center py-4">
              <div className="w-40 h-40 bg-surface-2/60 rounded-full" />
            </div>
            <div className="flex justify-center gap-4">
              <Bone className="h-3 w-16" />
              <Bone className="h-3 w-16" />
            </div>
          </div>
        </div>

        {/* Insight box */}
        <div className="rounded border border-surface-2 bg-surface-2/20 p-5 space-y-2.5 animate-pulse">
          <Bone className="h-3 w-28" />
          <Bone className="h-3 w-full" />
          <Bone className="h-3 w-11/12" />
          <Bone className="h-3 w-4/6" />
        </div>

        {/* Strengths & weaknesses */}
        <div className="grid grid-cols-2 gap-4 animate-pulse">
          {[0, 1].map((i) => (
            <div key={i} className="rounded bg-surface-2/40 p-3 space-y-1.5">
              <Bone className="h-2.5 w-36" />
              <Bone className="h-4 w-44" />
              <Bone className="h-2.5 w-24" />
            </div>
          ))}
        </div>

        {/* Archetype cards */}
        <div className="animate-pulse">
          <Bone className="h-3 w-60 mb-3" />
          <div className="flex gap-3">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="flex-1 min-w-[152px] rounded border border-surface-2 bg-surface-2/20 p-3 space-y-2"
              >
                <Bone className="h-3 w-24" />
                <Bone className="h-6 w-12" />
                <Bone className="h-1.5 w-full" />
                <Bone className="h-2.5 w-20" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Supporting analysis divider */}
      <div className="flex items-center gap-4 pt-2">
        <div className="h-px flex-1 bg-surface-2" />
        <Bone className="h-3 w-36 animate-pulse" />
        <div className="h-px flex-1 bg-surface-2" />
      </div>

      {/* 3-col grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Form */}
        <PanelSkeleton>
          <div className="flex items-center justify-between">
            <Bone className="h-4 w-12" />
            <div className="flex gap-1">
              {[...Array(5)].map((_, i) => <Bone key={i} className="w-6 h-6" />)}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-surface-2/40 rounded p-3 space-y-1">
                <Bone className="h-6 w-8" />
                <Bone className="h-3 w-12" />
              </div>
            ))}
          </div>
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex justify-between border-b border-surface-2 py-1.5">
                <Bone className="h-3 w-24" />
                <Bone className="h-3 w-8" />
              </div>
            ))}
          </div>
        </PanelSkeleton>

        {/* Identity */}
        <PanelSkeleton>
          <div className="flex items-center justify-between">
            <Bone className="h-4 w-32" />
            <Bone className="h-3 w-12" />
          </div>
          <div className="flex gap-2">
            <Bone className="h-3 w-16" />
            <Bone className="h-3 w-12" />
          </div>
          <div className="space-y-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Bone className="h-3 w-28 shrink-0" />
                <div className="flex-1 h-1 bg-surface-2 rounded" />
                <Bone className="h-3 w-14" />
              </div>
            ))}
          </div>
        </PanelSkeleton>

        {/* Referee */}
        <PanelSkeleton>
          <div className="flex items-center justify-between">
            <Bone className="h-4 w-16" />
            <Bone className="h-3 w-24" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-surface-2/40 rounded p-3 space-y-1">
                <Bone className="h-5 w-10" />
                <Bone className="h-3 w-20" />
              </div>
            ))}
          </div>
          <Bone className="h-3 w-full" />
        </PanelSkeleton>
      </div>

      {/* 2-col grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Player Cards */}
        <PanelSkeleton>
          <Bone className="h-4 w-24" />
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded border border-surface-2 p-3 space-y-2">
                <div className="flex justify-between">
                  <div className="space-y-1">
                    <Bone className="h-4 w-28" />
                    <Bone className="h-3 w-20" />
                  </div>
                  <Bone className="h-3 w-10" />
                </div>
                <div className="flex gap-4">
                  {[...Array(3)].map((_, j) => <Bone key={j} className="h-3 w-16" />)}
                </div>
              </div>
            ))}
          </div>
        </PanelSkeleton>

        {/* Game State */}
        <PanelSkeleton>
          <Bone className="h-4 w-44" />
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-surface-2/40 rounded p-3 space-y-2">
                <div className="flex justify-between">
                  <Bone className="h-3 w-20" />
                  <Bone className="h-3 w-16" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {[0, 1].map((j) => (
                    <div key={j} className="space-y-1">
                      <Bone className="h-3 w-16" />
                      <Bone className="h-4 w-10" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </PanelSkeleton>
      </div>

      {/* Gameplan */}
      <div className="rounded border border-accent/20 bg-surface p-6 space-y-5">
        <div className="space-y-2">
          <Bone className="h-3 w-20 animate-pulse" />
          <Bone className="h-6 w-96 max-w-full animate-pulse" />
        </div>
        <div className="space-y-2 animate-pulse">
          <Bone className="h-3 w-full" />
          <Bone className="h-3 w-full" />
          <Bone className="h-3 w-4/5" />
          <Bone className="h-3 w-full" />
          <Bone className="h-3 w-3/5" />
        </div>
        <div className="space-y-2 animate-pulse">
          <Bone className="h-3 w-28" />
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex gap-3">
              <Bone className="h-4 w-6 shrink-0" />
              <Bone className="h-4 flex-1" />
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
