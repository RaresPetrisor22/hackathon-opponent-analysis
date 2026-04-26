import type { PlayerCard, PlayerCardsSection } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

interface Props {
  data: PlayerCardsSection;
}

const THREAT_COLORS: Record<string, string> = {
  high: "border-danger/40 bg-danger/5",
  medium: "border-warning/40 bg-warning/5",
  low: "border-surface-2 bg-surface",
};

const THREAT_BADGE: Record<string, string> = {
  high: "text-danger",
  medium: "text-warning",
  low: "text-muted-fg",
};

function Card({ player }: { player: PlayerCard }) {
  return (
    <div
      className={`rounded border p-3 space-y-2 ${THREAT_COLORS[player.threat_level] ?? "border-surface-2"}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-sm text-white">{player.name}</p>
          <p className="text-xs text-muted-fg">
            {player.position}
            {player.jersey_number != null && ` · #${player.jersey_number}`}
          </p>
        </div>
        <Badge
          className={`text-[10px] font-mono uppercase ${THREAT_BADGE[player.threat_level] ?? ""} border-0 bg-transparent px-0`}
        >
          {player.threat_level}
        </Badge>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {Object.entries(player.key_stats).map(([k, v]) => (
          <div key={k} className="text-xs">
            <span className="text-muted-fg">{k}: </span>
            <span className="font-mono text-white">{typeof v === "number" ? v.toFixed(1) : v}</span>
          </div>
        ))}
      </div>

      {player.notes && (
        <p className="text-[11px] text-muted-fg">{player.notes}</p>
      )}
    </div>
  );
}

export function PlayerCards({ data }: Props) {
  return (
    <div className="rounded-xl border border-surface-2 bg-surface p-5 space-y-5">
      <div className="flex items-center gap-2.5">
        <span className="h-3.5 w-[3px] bg-accent rounded-sm" />
        <h2 className="font-mono text-xs font-semibold text-white uppercase tracking-[0.22em]">
          Player Cards
        </h2>
      </div>

      {data.llm_summary && (
        <div className="border-b border-surface-2 pb-4 space-y-1">
          <p className="text-[10px] font-mono text-accent uppercase tracking-widest">Analyst Take</p>
          <p className="text-xs text-white leading-relaxed">{data.llm_summary}</p>
        </div>
      )}

      <div>
        <p className="text-xs text-muted-fg uppercase tracking-widest font-mono mb-3">
          Key Threats
        </p>
        <div className="space-y-2">
          {data.key_threats.map((p) => (
            <Card key={p.player_id} player={p} />
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs text-muted-fg uppercase tracking-widest font-mono mb-3">
          Vulnerabilities
        </p>
        <div className="space-y-2">
          {data.defensive_vulnerabilities.map((p) => (
            <Card key={p.player_id} player={p} />
          ))}
        </div>
      </div>
    </div>
  );
}
