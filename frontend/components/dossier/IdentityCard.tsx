import type { IdentitySection } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { RadarFingerprint } from "@/components/charts/RadarFingerprint";

interface Props {
  data: IdentitySection;
}

const INTENSITY_COLORS: Record<string, string> = {
  high: "text-danger",
  medium: "text-warning",
  low: "text-accent",
};

function buildRadarData(stats: IdentitySection["stats"]) {
  return [
    { metric: "Possession", value: stats.avg_possession, fullMark: 100 },
    { metric: "Pass Acc.", value: stats.avg_pass_accuracy, fullMark: 100 },
    { metric: "Shots", value: stats.avg_shots, fullMark: 22 },
    { metric: "On Target", value: stats.avg_shots_on_target, fullMark: 10 },
    { metric: "Corners", value: stats.avg_corners, fullMark: 10 },
    { metric: "Fouls", value: stats.avg_fouls, fullMark: 20 },
  ];
}

export function IdentityCard({ data }: Props) {
  const stats = data.stats;

  return (
    <div className="rounded border border-surface-2 bg-surface p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-base">Tactical Identity</h2>
        <span className="text-xs font-mono text-muted-fg">
          {stats.preferred_formation}
        </span>
      </div>

      <div className="flex gap-2 items-center">
        <span className="text-xs text-muted-fg">Press:</span>
        <Badge className={`text-[10px] font-mono uppercase border-0 bg-transparent px-0 ${INTENSITY_COLORS[data.pressing_intensity] ?? ""}`}>
          {data.pressing_intensity}
        </Badge>
        <span className="mx-2 text-surface-2">|</span>
        <span className="text-xs text-muted-fg">Style:</span>
        <span className="text-xs font-medium text-white">{data.play_style}</span>
      </div>

      {/* Tactical fingerprint radar */}
      <div>
        <p className="text-[10px] font-mono text-muted-fg uppercase tracking-widest mb-1">
          Tactical fingerprint
        </p>
        <RadarFingerprint data={buildRadarData(stats)} height={200} />
      </div>

      <div className="space-y-2">
        <StatBar label="Possession" value={stats.avg_possession} max={100} unit="%" />
        <StatBar label="Pass acc" value={stats.avg_pass_accuracy} max={100} unit="%" />
        <StatBar label="Shots" value={stats.avg_shots} max={22} unit="/game" />
        <StatBar label="Shots on target" value={stats.avg_shots_on_target} max={10} unit="/game" />
        <StatBar label="Fouls" value={stats.avg_fouls} max={20} unit="/game" />
        <StatBar label="Corners" value={stats.avg_corners} max={10} unit="/game" />
      </div>

      {data.notes && (
        <p className="text-xs text-muted-fg border-t border-surface-2 pt-3">{data.notes}</p>
      )}
    </div>
  );
}

function StatBar({
  label,
  value,
  max,
  unit,
}: {
  label: string;
  value: number;
  max: number;
  unit: string;
}) {
  const pct = Math.min((value / max) * 100, 100);

  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="text-muted-fg w-28 shrink-0">{label}</span>
      <div className="flex-1 h-1 bg-surface-2 rounded overflow-hidden">
        <div className="h-full bg-accent/60 rounded" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-white w-16 text-right">
        {value.toFixed(1)}
        <span className="text-muted-fg text-[10px] ml-0.5">{unit}</span>
      </span>
    </div>
  );
}
