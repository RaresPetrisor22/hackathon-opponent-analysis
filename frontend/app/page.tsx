"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect, useMemo } from "react";
import { fetchTeams } from "@/lib/api";
import type { TeamSummary } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// FC Universitatea Cluj — API-Football team ID. Matches backend settings.fcu_team_id.
// We exclude FCU from the opponent dropdown since they cannot scout themselves.
const FCU_API_FOOTBALL_ID = 2599;

export default function HomePage() {
  const router = useRouter();
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchTeams().then(setTeams).catch(console.error);
  }, []);

  // Drop FCU from the opponent list — they cannot be their own opponent.
  const opponents = useMemo(
    () => teams.filter((t) => t.api_football_id !== FCU_API_FOOTBALL_ID),
    [teams],
  );

  function handleGenerate() {
    if (!selectedId) return;
    setLoading(true);
    router.push(`/dossier/${selectedId}`);
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] gap-8 px-4">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Next Opponent</h1>
        <p className="text-muted-fg mt-2 text-sm">
          Select the team from the dropdown to generate the pre-match dossier.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 w-full max-w-md">
        <Select value={selectedId} onValueChange={setSelectedId}>
          <SelectTrigger className="flex-1 bg-surface border-surface-2 text-white h-10">
            <SelectValue placeholder="Select opponent..." />
          </SelectTrigger>
          <SelectContent
            position="popper"
            side="bottom"
            sideOffset={4}
            avoidCollisions={false}
            className="!max-h-[230px] overflow-y-auto"
          >
            {opponents.map((t) => (
              <SelectItem key={t.id} value={String(t.id)}>
                <span className="flex items-center gap-2">
                  {t.logo_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={t.logo_url} alt="" width={18} height={18} className="object-contain shrink-0" />
                  )}
                  {t.name}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          onClick={handleGenerate}
          disabled={!selectedId || loading}
          className="h-10 px-6 bg-accent text-background font-medium hover:bg-accent-dim disabled:opacity-40"
        >
          {loading ? "Loading..." : "Generate Dossier"}
        </Button>
      </div>
    </div>
  );
}
