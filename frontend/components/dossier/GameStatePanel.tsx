import type { GameStateSection } from "@/lib/types";

interface Props {
  data: GameStateSection;
}

const STATE_COLORS: Record<string, string> = {
  winning: "text-accent",
  drawing: "text-warning",
  losing: "text-danger",
};

export function GameStatePanel({ data }: Props) {
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
    </div>
  );
}
