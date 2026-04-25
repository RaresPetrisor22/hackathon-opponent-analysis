"use client";

import { useEffect, useState } from "react";
import { ChevronDown, User } from "lucide-react";
import type { RefereeSection } from "@/lib/types";
import { fetchRefereeNames, fetchRefereeStats } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Props {
  data: RefereeSection;
}

export function RefereeCard({ data }: Props) {
  const [names, setNames] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>(data.referee_name ?? "");
  const [stats, setStats] = useState<RefereeSection>(data);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchRefereeNames()
      .then((list) => {
        if (data.referee_name && !list.includes(data.referee_name)) {
          setNames([data.referee_name, ...list]);
        } else {
          setNames(list);
        }
      })
      .catch(() => {});
  }, [data.referee_name]);

  async function handleSelect(name: string) {
    setSelected(name);
    if (name === data.referee_name) {
      setStats(data);
      return;
    }
    setLoading(true);
    try {
      setStats(await fetchRefereeStats(name));
    } catch {
      // keep existing stats on error
    } finally {
      setLoading(false);
    }
  }

  const isAssigned = selected === data.referee_name && !!data.referee_name;

  return (
    <div className="rounded border border-surface-2 bg-surface p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-base">Referee</h2>
        {isAssigned && (
          <span className="text-[10px] font-mono text-accent uppercase tracking-widest border border-accent/30 rounded px-1.5 py-0.5">
            assigned
          </span>
        )}
      </div>

      {/* Dropdown */}
      <Select value={selected} onValueChange={handleSelect}>
        <SelectTrigger
          className="
            w-full h-10 px-3 rounded-md
            bg-[#0d1424] border border-surface-2
            text-sm text-white
            hover:border-accent/40 hover:bg-[#0d1424]
            focus:outline-none focus:border-accent/60 focus:ring-0
            data-placeholder:text-muted-fg
            transition-colors
          "
        >
          <div className="flex items-center gap-2 min-w-0">
            <User className="size-3.5 shrink-0 text-muted-fg" />
            <SelectValue placeholder="Select a referee..." />
          </div>
        </SelectTrigger>
        <SelectContent
          className="
            bg-[#0d1424] border border-surface-2
            text-white rounded-md shadow-xl
            min-w-[var(--radix-select-trigger-width)]
          "
        >
          {names.map((name) => (
            <SelectItem
              key={name}
              value={name}
              className="
                text-sm text-white
                focus:bg-surface-2 focus:text-white
                data-[state=checked]:text-accent
                cursor-pointer rounded
              "
            >
              <span className="flex items-center gap-2">
                {name}
                {name === data.referee_name && (
                  <span className="text-accent text-[10px] font-mono tracking-widest">
                    assigned
                  </span>
                )}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Stats or empty state */}
      {loading ? (
        <div className="grid grid-cols-2 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-surface-2 rounded p-3 animate-pulse h-14" />
          ))}
        </div>
      ) : stats.total_matches === 0 ? (
        <p className="text-xs text-muted-fg">{stats.notes}</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <StatBox label="Yellows / game" value={stats.avg_yellow_cards.toFixed(1)} />
            <StatBox label="Reds / game" value={stats.avg_red_cards.toFixed(2)} />
            <StatBox label="Fouls / game" value={stats.avg_fouls_called.toFixed(1)} />
            <StatBox
              label="Home factor"
              value={
                stats.home_advantage_factor != null
                  ? stats.home_advantage_factor.toFixed(2)
                  : "N/A"
              }
            />
          </div>
          <p className="text-xs text-muted-fg leading-relaxed">{stats.notes}</p>
        </>
      )}
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
