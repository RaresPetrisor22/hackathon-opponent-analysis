"use client";

import { useState } from "react";
import type { ArchetypeRecord, MatchupSection, TacticalIdentityStats } from "@/lib/types";
import {
  Legend,
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";

interface Props {
  data: MatchupSection;
  opponentIdentity: TacticalIdentityStats;
  opponentName: string;
}

function WinRateBar({ wins, draws, losses }: { wins: number; draws: number; losses: number }) {
  const total = wins + draws + losses || 1;
  return (
    <div className="flex h-1.5 rounded overflow-hidden gap-px w-full">
      <div className="bg-accent" style={{ width: `${(wins / total) * 100}%` }} />
      <div className="bg-warning" style={{ width: `${(draws / total) * 100}%` }} />
      <div className="bg-danger" style={{ width: `${(losses / total) * 100}%` }} />
    </div>
  );
}

function getVerdict(winRate: number): { label: string; color: string; bg: string } {
  if (winRate < 35)
    return { label: "Favourable", color: "text-accent", bg: "bg-accent/10 border-accent/30" };
  if (winRate < 50)
    return { label: "Balanced", color: "text-warning", bg: "bg-warning/10 border-warning/30" };
  return { label: "Challenging", color: "text-danger", bg: "bg-danger/10 border-danger/30" };
}

const RADAR_AXES: { key: keyof TacticalIdentityStats; label: string; min: number; max: number }[] = [
  { key: "avg_possession", label: "Possession", min: 30, max: 70 },
  { key: "avg_pass_accuracy", label: "Passing", min: 60, max: 92 },
  { key: "avg_shots_on_target", label: "Shot Threat", min: 0, max: 8 },
  { key: "avg_corners", label: "Corners", min: 0, max: 10 },
  { key: "avg_fouls", label: "Pressing", min: 8, max: 20 },
];

function norm(value: number, min: number, max: number): number {
  return Math.round(Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100)));
}

function TacticalRadar({
  opponentStats,
  fcuStats,
  opponentName,
}: {
  opponentStats: TacticalIdentityStats;
  fcuStats: TacticalIdentityStats | null;
  opponentName: string;
}) {
  const data = RADAR_AXES.map(({ key, label, min, max }) => ({
    metric: label,
    opponent: norm(opponentStats[key] as number, min, max),
    fcu: fcuStats ? norm(fcuStats[key] as number, min, max) : undefined,
    fullMark: 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={230}>
      <RadarChart data={data} margin={{ top: 20, right: 36, bottom: 20, left: 36 }}>
        <PolarGrid stroke="#1a2747" />
        <PolarAngleAxis
          dataKey="metric"
          tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "ui-monospace, monospace" }}
        />
        <Radar
          name={opponentName}
          dataKey="opponent"
          stroke="#f87171"
          fill="#f87171"
          fillOpacity={0.15}
          strokeWidth={1.5}
        />
        {fcuStats && (
          <Radar
            name="U Cluj"
            dataKey="fcu"
            stroke="#60a5fa"
            fill="#60a5fa"
            fillOpacity={0.18}
            strokeWidth={2}
          />
        )}
        <Legend
          iconSize={8}
          wrapperStyle={{ fontSize: 10, fontFamily: "ui-monospace, monospace", paddingTop: 4 }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
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
  const rateColor =
    winRate >= 50 ? "text-danger" : winRate >= 35 ? "text-warning" : "text-accent";

  return (
    <button
      onClick={onClick}
      className={`flex-1 min-w-[152px] text-left rounded border p-3 transition-all space-y-2 ${
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
      <p className={`font-mono text-xl font-bold ${rateColor}`}>{winRate}%</p>
      <WinRateBar wins={record.wins} draws={record.draws} losses={record.losses} />
      <p className="font-mono text-[10px] text-muted-fg">
        {record.wins}W · {record.draws}D · {record.losses}L
      </p>
    </button>
  );
}

export function MatchupIntelligence({ data, opponentIdentity, opponentName }: Props) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const active =
    activeId != null ? data.archetypes.find((a) => a.archetype_id === activeId) : null;

  const fcuArchetype = data.archetypes.find((a) => a.archetype_id === data.fcu_archetype_id);
  const fcuTotal = fcuArchetype
    ? fcuArchetype.wins + fcuArchetype.draws + fcuArchetype.losses || 1
    : 1;
  const fcuWinRate = fcuArchetype ? Math.round((fcuArchetype.wins / fcuTotal) * 100) : 0;
  const verdict = getVerdict(fcuWinRate);

  const bestMatchup = [...data.archetypes].sort(
    (a, b) =>
      a.wins / (a.wins + a.draws + a.losses || 1) -
      b.wins / (b.wins + b.draws + b.losses || 1)
  )[0];

  const worstMatchup = [...data.archetypes].sort(
    (a, b) =>
      b.wins / (b.wins + b.draws + b.losses || 1) -
      a.wins / (a.wins + a.draws + a.losses || 1)
  )[0];

  const bestTotal = bestMatchup ? bestMatchup.wins + bestMatchup.draws + bestMatchup.losses || 1 : 1;
  const bestWinRate = bestMatchup ? Math.round((bestMatchup.wins / bestTotal) * 100) : 0;
  const bestLossRate = 100 - bestWinRate;

  const worstWinRate = worstMatchup
    ? Math.round(
        (worstMatchup.wins /
          (worstMatchup.wins + worstMatchup.draws + worstMatchup.losses || 1)) *
          100
      )
    : 0;

  return (
    <div
      className="rounded-xl border border-accent/30 bg-surface bg-card-gradient p-6 space-y-6"
      style={{ boxShadow: "0 0 56px rgba(96, 165, 250, 0.10), inset 0 1px 0 0 rgba(255,255,255,0.05)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono text-accent uppercase tracking-widest px-2 py-1 rounded border border-accent/30 bg-accent/10">
            Core Analysis
          </span>
          <h2 className="text-xl font-bold text-white">Matchup Intelligence</h2>
        </div>
        <span className="text-xs font-mono text-muted-fg hidden sm:block">2024-25 season data</span>
      </div>

      {/* Hero grid: winning condition + radar */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Winning Condition — 3 cols */}
        <div className="lg:col-span-3 rounded border border-accent/40 bg-accent/5 p-6 space-y-5">
          <p className="text-[10px] font-mono text-accent uppercase tracking-widest">
            Recommended Approach
          </p>

          <div className="flex items-start gap-6">
            {/* Big percentage */}
            <div className="shrink-0">
              <p className="font-mono text-8xl font-bold leading-none text-accent">
                {bestLossRate}%
              </p>
              <p className="font-mono text-xs text-muted-fg mt-2">{opponentName} loss rate</p>
            </div>

            <div className="w-px self-stretch bg-accent/20" />

            {/* Tactical recommendation */}
            <div className="space-y-2 flex-1 min-w-0">
              <p className="text-[10px] font-mono text-muted-fg uppercase tracking-widest">
                Play like
              </p>
              <p className="text-2xl font-bold text-white leading-tight">
                {bestMatchup?.archetype_name}
              </p>
              {bestMatchup?.archetype_id === data.fcu_archetype_id ? (
                <p className="text-xs font-mono text-accent">
                  Matches your natural style — a double advantage.
                </p>
              ) : (
                <p className="text-xs text-muted-fg leading-relaxed line-clamp-2">
                  {bestMatchup?.archetype_description}
                </p>
              )}
              <span
                className={`inline-flex items-center text-[10px] font-mono uppercase tracking-widest px-2 py-1 rounded border ${verdict.bg} ${verdict.color}`}
              >
                {verdict.label} Matchup
              </span>
            </div>
          </div>

          {bestMatchup && (
            <div className="space-y-1.5">
              <WinRateBar
                wins={bestMatchup.wins}
                draws={bestMatchup.draws}
                losses={bestMatchup.losses}
              />
              <p className="font-mono text-xs text-muted-fg">
                {bestMatchup.wins}W · {bestMatchup.draws}D · {bestMatchup.losses}L across{" "}
                {bestMatchup.matches_played} matches
              </p>
            </div>
          )}
        </div>

        {/* Tactical vulnerability radar — 2 cols */}
        <div className="lg:col-span-2 rounded border border-surface-2 bg-surface-2/20 p-4 flex flex-col">
          <p className="text-[10px] font-mono text-muted-fg uppercase tracking-widest mb-0.5">
            Tactical Fingerprint
          </p>
          <p className="text-[10px] text-muted-fg mb-1">
            <span className="text-accent font-mono font-bold">Green</span> = U Cluj ·{" "}
            <span className="text-danger font-mono font-bold">Red</span> = {opponentName}
          </p>
          <div className="flex-1">
            <TacticalRadar
              opponentStats={opponentIdentity}
              fcuStats={data.fcu_tactical_profile}
              opponentName={opponentName}
            />
          </div>
        </div>
      </div>

      {/* Prediction summary + analyst take */}
      {(data.prediction_summary || data.llm_insight) && (
        <div className="rounded border border-surface-2 bg-surface-2/40 p-5 space-y-4">
          {data.prediction_summary && (
            <div>
              <p className="text-[10px] font-mono text-muted-fg uppercase tracking-widest mb-3">
                Matchup Insight
              </p>
              <div className="space-y-3 text-sm text-white leading-relaxed max-w-3xl">
                {data.prediction_summary.split(/\n\s*\n/).map((para, i) => (
                  <p key={i}>{para.trim()}</p>
                ))}
              </div>
            </div>
          )}
          {data.llm_insight && (
            <div className={data.prediction_summary ? "border-t border-surface-2 pt-4 space-y-1" : "space-y-1"}>
              <p className="text-[10px] font-mono text-accent uppercase tracking-widest">Analyst Take</p>
              <p className="text-sm text-white leading-relaxed max-w-3xl">{data.llm_insight}</p>
            </div>
          )}
        </div>
      )}

      {/* Strengths & weaknesses */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded bg-surface-2 p-3 space-y-1">
          <p className="text-[10px] font-mono text-accent uppercase tracking-widest">
            They struggle most against
          </p>
          <p className="text-sm font-semibold text-white">{bestMatchup?.archetype_name}</p>
          <p className="text-xs text-muted-fg">
            {bestWinRate}% win rate · {bestMatchup?.matches_played} matches
          </p>
        </div>
        <div className="rounded bg-surface-2 p-3 space-y-1">
          <p className="text-[10px] font-mono text-danger uppercase tracking-widest">
            They are strongest against
          </p>
          <p className="text-sm font-semibold text-white">{worstMatchup?.archetype_name}</p>
          <p className="text-xs text-muted-fg">
            {worstWinRate}% win rate · {worstMatchup?.matches_played} matches
          </p>
        </div>
      </div>

      {/* Archetype breakdown */}
      <div>
        <p className="text-xs text-muted-fg uppercase tracking-widest font-mono mb-3">
          {opponentName} win rate against every playing style
        </p>
        <div className="flex gap-3 overflow-x-auto pb-1">
          {data.archetypes.map((record) => (
            <ArchetypeCard
              key={record.archetype_id}
              record={record}
              isActive={activeId === record.archetype_id}
              isFcu={record.archetype_id === data.fcu_archetype_id}
              onClick={() =>
                setActiveId(activeId === record.archetype_id ? null : record.archetype_id)
              }
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
            <StatBlock label="Goals scored/game" value={active.goals_for.toFixed(2)} />
            <StatBlock label="Goals conceded/game" value={active.goals_against.toFixed(2)} />
            <StatBlock
              label="Win rate"
              value={
                active.matches_played > 0
                  ? `${Math.round((active.wins / active.matches_played) * 100)}%`
                  : "—"
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}

function StatBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-fg text-xs">{label}</p>
      <p className="font-mono text-white text-base mt-0.5">{value}</p>
    </div>
  );
}
