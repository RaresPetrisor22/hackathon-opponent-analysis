import { Fragment } from "react";
import type { GameStateSection, PlayerSummary } from "@/lib/types";

interface Props {
  data: GameStateSection;
  roster?: PlayerSummary[];
}

const STATE_COLORS: Record<string, string> = {
  winning: "text-accent",
  drawing: "text-warning",
  losing: "text-danger",
};

const POSITION_GROUPS: { key: string; label: string; matches: string[] }[] = [
  { key: "Attacker", label: "Attackers", matches: ["F", "A", "FW", "ATT", "Attacker", "Forward"] },
  { key: "Midfielder", label: "Midfielders", matches: ["M", "MID", "Midfielder"] },
  { key: "Defender", label: "Defenders", matches: ["D", "DEF", "Defender"] },
  { key: "Goalkeeper", label: "Goalkeepers", matches: ["G", "GK", "Goalkeeper"] },
];

const POSITION_ACCENT: Record<string, string> = {
  Goalkeeper: "text-warning",
  Defender: "text-accent",
  Midfielder: "text-white",
  Attacker: "text-danger",
};

function POSITION_LABEL(raw: string | null): string {
  if (!raw) return "-";
  const map: Record<string, string> = {
    G: "Goalkeeper",
    GK: "Goalkeeper",
    D: "Defender",
    DEF: "Defender",
    M: "Midfielder",
    MID: "Midfielder",
    F: "Attacker",
    A: "Attacker",
    FW: "Attacker",
    ATT: "Attacker",
  };
  return map[raw] ?? raw;
}

function RosterTable({ roster }: { roster: PlayerSummary[] }) {
  // Bucket players by position; anything unclassified goes to "Other"
  const grouped = POSITION_GROUPS.map((g) => ({
    key: g.key,
    label: g.label,
    players: roster.filter((p) => !!p.position && g.matches.includes(p.position)),
  }));
  const classifiedIds = new Set(grouped.flatMap((g) => g.players.map((p) => p.id)));
  const others = roster.filter((p) => !classifiedIds.has(p.id));
  if (others.length > 0) {
    grouped.push({ key: "Other", label: "Other", players: others });
  }

  // Running sequential counter so each player gets a unique index across all groups
  let counter = 0;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[10px] font-mono uppercase tracking-widest text-muted-fg border-b border-surface-2">
            <th className="py-2 pr-3 w-10">#</th>
            <th className="py-2 pr-3">Name</th>
            <th className="py-2 pr-3">Position</th>
          </tr>
        </thead>
        <tbody>
          {grouped.map((group) =>
            group.players.length === 0 ? null : (
              <Fragment key={group.key}>
                <tr className="bg-surface-2/40">
                  <td
                    colSpan={3}
                    className={`py-1.5 px-3 text-[10px] font-mono uppercase tracking-widest ${
                      POSITION_ACCENT[group.key] ?? "text-muted-fg"
                    }`}
                  >
                    {group.label}{" "}
                    <span className="text-muted-fg">({group.players.length})</span>
                  </td>
                </tr>
                {group.players.map((p) => {
                  counter += 1;
                  return (
                    <tr
                      key={p.id}
                      className="border-b border-surface-2/40 hover:bg-surface-2/30 transition-colors"
                    >
                      <td className="py-1.5 pr-3 font-mono text-muted-fg">
                        {counter}
                      </td>
                      <td className="py-1.5 pr-3 text-white">{p.name}</td>
                      <td className="py-1.5 pr-3 text-muted-fg">
                        {POSITION_LABEL(p.position)}
                      </td>
                    </tr>
                  );
                })}
              </Fragment>
            ),
          )}
        </tbody>
      </table>
    </div>
  );
}

export function GameStatePanel({ data, roster }: Props) {
  return (
    <div className="rounded border border-surface-2 bg-surface p-5 space-y-4">
      <h2 className="font-semibold text-base">Game State Intelligence</h2>

      <div className="space-y-3">
        {data.records.map((r) => (
          <div key={r.state} className="bg-surface-2 rounded p-3">
            <div className="flex items-center justify-between mb-2">
              <span
                className={`text-xs font-mono font-medium uppercase ${STATE_COLORS[r.state] ?? ""}`}
              >
                When {r.state}
              </span>
              <span className="text-xs text-muted-fg">{r.matches} matches</span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <p className="text-muted-fg">Avg scored</p>
                <p className="font-mono text-white">{r.avg_goals_for.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-muted-fg">Avg conceded</p>
                <p className="font-mono text-white">{r.avg_goals_against.toFixed(2)}</p>
              </div>
            </div>
            <div className="mt-2 text-[11px] text-muted-fg space-y-0.5">
              <p>Def: {r.defensive_change}</p>
              <p>Off: {r.offensive_change}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-surface-2 pt-3 space-y-1 text-xs">
        <p>
          <span className="text-muted-fg">When losing: </span>
          <span className="text-white">{data.tendency_when_losing}</span>
        </p>
        <p>
          <span className="text-muted-fg">When winning: </span>
          <span className="text-white">{data.tendency_when_winning}</span>
        </p>
      </div>

      {roster && roster.length > 0 && (
        <div className="border-t border-surface-2 pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-mono text-muted-fg uppercase tracking-widest">
              Opponent Squad
            </p>
            <span className="text-[10px] font-mono text-muted-fg">
              {roster.length} players
            </span>
          </div>
          <RosterTable roster={roster} />
        </div>
      )}
    </div>
  );
}
