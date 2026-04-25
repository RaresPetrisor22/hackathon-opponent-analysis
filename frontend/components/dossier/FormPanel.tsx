import type { FormSection } from "@/lib/types";

interface Props {
  data: FormSection;
}

const RESULT_COLORS: Record<string, string> = {
  W: "bg-accent text-background",
  D: "bg-warning text-background",
  L: "bg-danger text-white",
};

export function FormPanel({ data }: Props) {
  return (
    <div className="rounded border border-surface-2 bg-surface p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-base">Form</h2>
        <div className="flex gap-1">
          {data.form_string.split("").map((r, i) => (
            <span
              key={i}
              className={`w-6 h-6 rounded text-[11px] font-mono font-semibold flex items-center justify-center ${RESULT_COLORS[r] ?? "bg-muted"}`}
            >
              {r}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <StatBox label="Wins" value={data.wins_last5} />
        <StatBox label="Draws" value={data.draws_last5} />
        <StatBox label="Losses" value={data.losses_last5} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <StatRow label="Avg scored" value={data.goals_scored_avg.toFixed(1)} />
        <StatRow label="Avg conceded" value={data.goals_conceded_avg.toFixed(1)} />
      </div>

      <table className="w-full text-xs">
        <thead>
          <tr className="text-muted-fg border-b border-surface-2">
            <th className="text-left py-1 font-normal">Opponent</th>
            <th className="py-1 font-normal">H/A</th>
            <th className="py-1 font-normal">Score</th>
            <th className="py-1 font-normal">Res</th>
          </tr>
        </thead>
        <tbody>
          {data.last_5.map((m, i) => (
            <tr key={i} className="border-b border-surface-2 last:border-0">
              <td className="py-1.5 pr-2 truncate max-w-[100px]">{m.opponent}</td>
              <td className="py-1.5 text-center text-muted-fg">{m.home_away}</td>
              <td className="py-1.5 text-center font-mono">
                {m.goals_for}–{m.goals_against}
              </td>
              <td className="py-1.5 text-center">
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${RESULT_COLORS[m.result] ?? ""}`}
                >
                  {m.result}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {data.llm_summary && (
        <div className="border-t border-surface-2 pt-3 space-y-1">
          <p className="text-[10px] font-mono text-accent uppercase tracking-widest">Analyst Take</p>
          <p className="text-xs text-white leading-relaxed">{data.llm_summary}</p>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-surface-2 rounded p-3">
      <p className="font-mono text-2xl font-semibold text-white">{value}</p>
      <p className="text-muted-fg text-xs mt-0.5">{label}</p>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-muted-fg">{label}</span>
      <span className="font-mono text-white">{value}</span>
    </div>
  );
}
