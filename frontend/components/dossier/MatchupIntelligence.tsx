"use client";

import { useState } from "react";
import type { ArchetypeRecord, MatchupSection } from "@/lib/types";

interface Props {
  data: MatchupSection;
}

const RESULT_BAR_WIDTH = (wins: number, draws: number, losses: number) => {
  const total = wins + draws + losses || 1;
  return {
    w: Math.round((wins / total) * 100),
    d: Math.round((draws / total) * 100),
    l: Math.round((losses / total) * 100),
  };
};

function ArchetypeCard({
  record,
  isActive,
  isFcu,
  onClick,
}: {
  record: ArchetypeRecord;
  isActive: boolean;
  isFcu: boolean;
  onClick: () => void;
}) {
  const bar = RESULT_BAR_WIDTH(record.wins, record.draws, record.losses);

  return (
    <button
      onClick={onClick}
      className={`flex-1 min-w-[160px] text-left rounded border p-4 transition-all ${
        isActive
          ? "border-accent bg-surface-2"
          : "border-surface-2 bg-surface hover:border-muted"
      }`}
    >
      {isFcu && (
        <span className="text-[10px] font-mono text-accent uppercase tracking-widest block mb-1">
          U Cluj archetype
        </span>
      )}
      <p className="font-medium text-sm text-white">{record.archetype_name}</p>
      <p className="text-xs text-muted-fg mt-1 line-clamp-2">
        {record.archetype_description}
      </p>

      <div className="mt-3 flex h-1.5 rounded overflow-hidden gap-px">
        <div
          className="bg-accent h-full"
          style={{ width: `${bar.w}%` }}
          title={`${record.wins}W`}
        />
        <div
          className="bg-warning h-full"
          style={{ width: `${bar.d}%` }}
          title={`${record.draws}D`}
        />
        <div
          className="bg-danger h-full"
          style={{ width: `${bar.l}%` }}
          title={`${record.losses}L`}
        />
      </div>

      <p className="font-mono text-xs text-muted-fg mt-2">
        {record.wins}W {record.draws}D {record.losses}L
        <span className="ml-2">({record.matches_played} played)</span>
      </p>
    </button>
  );
}

export function MatchupIntelligence({ data }: Props) {
  const [activeId, setActiveId] = useState<number>(data.archetypes[0]?.archetype_id ?? -1);
  const active = data.archetypes.find((a) => a.archetype_id === activeId);

  return (
    <div className="rounded border border-surface-2 bg-surface p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-base">Matchup Intelligence</h2>
        <span className="text-xs font-mono text-muted-fg">archetype analysis</span>
      </div>

      {/* U Cluj prediction banner */}
      <div className="rounded bg-surface-2 border border-accent/20 px-4 py-3">
        <p className="text-xs text-muted-fg uppercase tracking-widest font-mono mb-1">
          Predicted matchup
        </p>
        <p className="text-sm text-white">{data.prediction_summary}</p>
        <p className="text-xs text-accent mt-1 font-mono">
          U Cluj plays as: {data.fcu_archetype_name}
        </p>
      </div>

      {/* Archetype cards row */}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {data.archetypes.map((record) => (
          <ArchetypeCard
            key={record.archetype_id}
            record={record}
            isActive={activeId === record.archetype_id}
            isFcu={record.archetype_id === data.fcu_archetype_id}
            onClick={() => setActiveId(record.archetype_id)}
          />
        ))}
      </div>

      {/* Detail panel for selected archetype */}
      {active && (
        <div className="rounded bg-surface-2 px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <Stat label="Goals for" value={active.goals_for.toFixed(2)} />
          <Stat label="Goals against" value={active.goals_against.toFixed(2)} />
          <Stat
            label="xG diff"
            value={active.xg_diff != null ? active.xg_diff.toFixed(2) : "N/A"}
          />
          <Stat
            label="Win rate"
            value={
              active.matches_played > 0
                ? `${Math.round((active.wins / active.matches_played) * 100)}%`
                : "—"
            }
          />
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-fg text-xs">{label}</p>
      <p className="font-mono text-white text-base mt-0.5">{value}</p>
    </div>
  );
}
