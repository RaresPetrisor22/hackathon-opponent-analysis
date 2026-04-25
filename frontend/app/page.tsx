"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
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

export default function HomePage() {
  const router = useRouter();
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchTeams().then(setTeams).catch(console.error);
  }, []);

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
          <SelectContent position="popper" sideOffset={4}>
            {teams.map((t) => (
              <SelectItem key={t.id} value={String(t.id)}>
                {t.name}
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
