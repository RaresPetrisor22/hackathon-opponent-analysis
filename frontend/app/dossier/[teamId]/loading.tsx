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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Bone className="h-7 w-48" />
          <Bone className="h-3 w-32" />
        </div>
      </div>

      {/* Matchup Intelligence hero */}
      <PanelSkeleton>
        <div className="flex items-center justify-between">
          <Bone className="h-4 w-40" />
          <Bone className="h-3 w-24" />
        </div>
        <Bone className="h-16 w-full rounded" />
        <div className="flex gap-3 overflow-hidden">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex-1 min-w-[160px] rounded border border-surface-2 p-4 space-y-3">
              <Bone className="h-3 w-24" />
              <Bone className="h-4 w-32" />
              <Bone className="h-1.5 w-full" />
              <Bone className="h-3 w-20" />
            </div>
          ))}
        </div>
        <Bone className="h-12 w-full" />
      </PanelSkeleton>

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
              <div key={i} className="bg-surface-2 rounded p-3 space-y-1">
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
                <Bone className="h-3 w-16" />
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
              <div key={i} className="bg-surface-2 rounded p-3 space-y-1">
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
              <div key={i} className="bg-surface-2 rounded p-3 space-y-2">
                <div className="flex justify-between">
                  <Bone className="h-3 w-20" />
                  <Bone className="h-3 w-16" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Bone className="h-3 w-16" />
                    <Bone className="h-4 w-10" />
                  </div>
                  <div className="space-y-1">
                    <Bone className="h-3 w-16" />
                    <Bone className="h-4 w-10" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </PanelSkeleton>
      </div>

      {/* Gameplan */}
      <div className="rounded border border-accent/20 bg-surface p-6 space-y-5">
        <div className="space-y-2">
          <Bone className="h-3 w-20" />
          <Bone className="h-6 w-96 max-w-full" />
        </div>
        <div className="space-y-2">
          <Bone className="h-3 w-full" />
          <Bone className="h-3 w-full" />
          <Bone className="h-3 w-4/5" />
          <Bone className="h-3 w-full" />
          <Bone className="h-3 w-3/5" />
        </div>
        <div className="space-y-2">
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
