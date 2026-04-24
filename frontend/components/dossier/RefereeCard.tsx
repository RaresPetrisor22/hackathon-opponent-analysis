import type { RefereeSection } from "@/lib/types";

interface Props {
  data: RefereeSection;
}

export function RefereeCard({ data }: Props) {
  return (
    <div className="rounded border border-surface-2 bg-surface p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-base">Referee</h2>
        {data.referee_name && (
          <span className="text-xs font-mono text-muted-fg">{data.referee_name}</span>
        )}
      </div>

      {!data.referee_name && (
        <p className="text-xs text-muted-fg">Referee not yet assigned.</p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <StatBox label="Yellows/game" value={data.avg_yellow_cards.toFixed(1)} />
        <StatBox label="Reds/game" value={data.avg_red_cards.toFixed(1)} />
        <StatBox label="Fouls/game" value={data.avg_fouls_called.toFixed(1)} />
        <StatBox
          label="Home factor"
          value={data.home_advantage_factor != null ? data.home_advantage_factor.toFixed(2) : "N/A"}
        />
      </div>

      <p className="text-xs text-muted-fg">{data.notes}</p>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-2 rounded p-3">
      <p className="font-mono text-lg font-semibold text-white">{value}</p>
      <p className="text-muted-fg text-xs mt-0.5">{label}</p>
    </div>
  );
}
