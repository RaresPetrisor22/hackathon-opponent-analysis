import type { GameplanNarrative as GameplanNarrativeType } from "@/lib/types";

interface Props {
  data: GameplanNarrativeType;
}

export function GameplanNarrative({ data }: Props) {
  return (
    <div className="rounded-xl border border-accent/25 bg-surface bg-card-gradient shadow-glow p-6 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-mono text-accent uppercase tracking-widest mb-2">
            Gameplan
          </p>
          <h2 className="text-lg font-semibold text-white leading-snug">{data.headline}</h2>
        </div>
      </div>

      <div
        className="prose prose-sm prose-invert max-w-none text-muted-fg leading-relaxed"
        dangerouslySetInnerHTML={{ __html: data.body.replace(/\n/g, "<br/>") }}
      />

      {data.key_actions.length > 0 && (
        <div>
          <p className="text-xs font-mono text-muted-fg uppercase tracking-widest mb-3">
            Coaching points
          </p>
          <ul className="space-y-2">
            {data.key_actions.map((action, i) => (
              <li key={i} className="flex gap-3 text-sm text-white">
                <span className="font-mono text-accent shrink-0">{String(i + 1).padStart(2, "0")}</span>
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
