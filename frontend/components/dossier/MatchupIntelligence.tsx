"use client";

import { useState } from "react";
import type { ArchetypeRecord, MatchupSection } from "@/lib/types";

interface Props {
  data: MatchupSection;
}

function WinRateBar({ wins, draws, losses }: { wins: number; draws: number; losses: number }) {
  const total = wins + draws + losses || 1;
  return (
    <div className="flex h-2 rounded overflow-hidden gap-px w-full">
      <div className="bg-accent" style={{ width: `${(wins / total) * 100}%` }} />
      <div className="bg-warning" style={{ width: `${(draws / total) * 100}%` }} />
      <div className="bg-danger" style={{ width: `${(losses / total) * 100}%` }} />
    </div>
  );
}

function getVerdict(winRate: number): {
  label: string;
  color: string;
  borderColor: string;
  summary: string;
} {
  if (winRate < 35) {
    return {
      label: "Favourable Matchup",
      color: "text-accent",
      borderColor: "border-accent/40",
      summary: `They win only ${winRate}% of games against teams that play like U Cluj — you hold the tactical edge.`,
    };
  }
  if (winRate < 50) {
    return {
      label: "Balanced Matchup",
      color: "text-warning",
      borderColor: "border-warning/40",
      summary: `They win ${winRate}% of games against teams that play like U Cluj — this will be a close tactical contest.`,
    };
  }
  return {
    label: "Challenging Matchup",
    color: "text-danger",
    borderColor: "border-danger/40",
    summary: `They win ${winRate}% of games against teams that play like U Cluj — prepare for a difficult tactical battle.`,
  };
}

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
  const total = record.wins + record.draws + record.losses || 1;
  const winRate = Math.round((record.wins / total) * 100);

  return (
    <button
      onClick={onClick}
      className={`flex-1 min-w-[150px] text-left rounded border p-3 transition-all space-y-2 ${
        isFcu
          ? "border-accent/50 bg-accent/5"
          : isActive
          ? "border-surface-2 bg-surface-2"
          : "border-surface-2 bg-surface hover:border-muted"
      }`}
    >
      {isFcu && (
        <span className="text-[9px] font-mono text-accent uppercase tracking-widest block">
          Your style
        </span>
      )}
      <p className="font-medium text-xs text-white leading-snug">{record.archetype_name}</p>
      <p className={`font-mono text-xl font-bold ${winRate >= 50 ? "text-danger" : winRate >= 35 ? "text-warning" : "text-accent"}`}>
        {winRate}%
      </p>
      <WinRateBar wins={record.wins} draws={record.draws} losses={record.losses} />
      <p className="font-mono text-[10px] text-muted-fg">
        {record.wins}W · {record.draws}D · {record.losses}L
      </p>
    </button>
  );
}

export function MatchupIntelligence({ data }: Props) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const active = activeId != null ? data.archetypes.find((a) => a.archetype_id === activeId) : null;

  const fcuArchetype = data.archetypes.find((a) => a.archetype_id === data.fcu_archetype_id);
  const fcuTotal = fcuArchetype
    ? fcuArchetype.wins + fcuArchetype.draws + fcuArchetype.losses || 1
    : 1;
  const fcuWinRate = fcuArchetype ? Math.round((fcuArchetype.wins / fcuTotal) * 100) : 0;
  const verdict = getVerdict(fcuWinRate);

  const bestMatchup = [...data.archetypes].sort(
    (a, b) => a.wins / (a.wins + a.draws + a.losses || 1) - b.wins / (b.wins + b.draws + b.losses || 1)
  )[0];
  const worstMatchup = [...data.archetypes].sort(
    (a, b) => b.wins / (b.wins + b.draws + b.losses || 1) - a.wins / (a.wins + a.draws + a.losses || 1)
  )[0];

  return (
    <div className={`rounded border ${verdict.borderColor} bg-surface p-6 space-y-6`}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Matchup Intelligence</h2>
        <span className="text-xs font-mono text-muted-fg">based on season match data</span>
      </div>

      {/* WINNING CONDITION — hero block */}
      <div className="rounded border border-accent/50 bg-accent/5 p-6 space-y-4">
        <span className="text-[10px] font-mono text-accent uppercase tracking-widest px-2 py-1 rounded border border-accent/30 bg-accent/10">
          Winning Condition
        </span>

        <div className="flex flex-col sm:flex-row sm:items-center gap-6">
          {/* The big number */}
          <div className="shrink-0 text-center sm:text-left">
            <p className="text-[10px] font-mono text-muted-fg uppercase tracking-widest mb-1">
              Opponent win rate vs this style
            </p>
            <p className="font-mono text-7xl font-bold leading-none text-accent">
              {bestMatchup
                ? Math.round((bestMatchup.wins / (bestMatchup.wins + bestMatchup.draws + bestMatchup.losses || 1)) * 100)
                : 0}%
            </p>
            {bestMatchup && (
              <p className="font-mono text-xs text-muted-fg mt-2">
                {bestMatchup.wins}W · {bestMatchup.draws}D · {bestMatchup.losses}L
                &nbsp;({bestMatchup.matches_played} games)
              </p>
            )}
            {bestMatchup && (
              <div className="mt-2 w-32">
                <WinRateBar
                  wins={bestMatchup.wins}
                  draws={bestMatchup.draws}
                  losses={bestMatchup.losses}
                />
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="hidden sm:block w-px self-stretch bg-accent/20" />

          {/* Tactical instruction */}
          <div className="space-y-3 flex-1">
            <div>
              <p className="text-[10px] font-mono text-muted-fg uppercase tracking-widest mb-1">
                Beat them by playing
              </p>
              <p className="text-2xl font-bold text-white">{bestMatchup?.archetype_name}</p>
              {bestMatchup?.archetype_id === data.fcu_archetype_id && (
                <p className="text-xs text-accent font-mono mt-1">
                  This is also U Cluj's natural style — a double advantage.
                </p>
              )}
            </div>
            <p className="text-sm text-white leading-relaxed">{data.prediction_summary}</p>
          </div>
        </div>
      </div>

      {/* Strengths & weaknesses */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded bg-surface-2 p-3 space-y-1">
          <p className="text-[10px] font-mono text-accent uppercase tracking-widest">
            They struggle most against
          </p>
          <p className="text-sm font-semibold text-white">{bestMatchup?.archetype_name}</p>
          <p className="text-xs text-muted-fg">
            {bestMatchup
              ? Math.round((bestMatchup.wins / (bestMatchup.wins + bestMatchup.draws + bestMatchup.losses || 1)) * 100)
              : 0}% win rate in {bestMatchup?.matches_played} games
          </p>
        </div>
        <div className="rounded bg-surface-2 p-3 space-y-1">
          <p className="text-[10px] font-mono text-danger uppercase tracking-widest">
            They are strongest against
          </p>
          <p className="text-sm font-semibold text-white">{worstMatchup?.archetype_name}</p>
          <p className="text-xs text-muted-fg">
            {worstMatchup
              ? Math.round((worstMatchup.wins / (worstMatchup.wins + worstMatchup.draws + worstMatchup.losses || 1)) * 100)
              : 0}% win rate in {worstMatchup?.matches_played} games
          </p>
        </div>
      </div>

      {/* Archetype breakdown */}
      <div>
        <p className="text-xs text-muted-fg uppercase tracking-widest font-mono mb-3">
          Their win rate against every playing style
        </p>
        <div className="flex gap-3 overflow-x-auto pb-1">
          {data.archetypes.map((record) => (
            <ArchetypeCard
              key={record.archetype_id}
              record={record}
              isActive={activeId === record.archetype_id}
              isFcu={record.archetype_id === data.fcu_archetype_id}
              onClick={() => setActiveId(activeId === record.archetype_id ? null : record.archetype_id)}
            />
          ))}
        </div>
      </div>

      {/* Detail panel */}
      {active && (
        <div className="rounded bg-surface-2 px-4 py-3 space-y-2">
          <p className="text-xs font-mono text-muted-fg uppercase tracking-widest">
            {active.archetype_name} — detail
          </p>
          <p className="text-xs text-muted-fg">{active.archetype_description}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-1">
            <Stat label="Goals scored/game" value={active.goals_for.toFixed(2)} />
            <Stat label="Goals conceded/game" value={active.goals_against.toFixed(2)} />
            <Stat label="xG diff" value={active.xg_diff != null ? active.xg_diff.toFixed(2) : "N/A"} />
            <Stat
              label="Win rate"
              value={active.matches_played > 0
                ? `${Math.round((active.wins / active.matches_played) * 100)}%`
                : "—"}
            />
          </div>
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
