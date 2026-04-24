"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { fetchTeams } from "@/lib/api";
import type { TeamSummary } from "@/lib/types";

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
        <select
          className="flex-1 bg-surface border border-surface-2 rounded px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-accent"
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
        >
          <option value="">Select opponent...</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>

        <button
          onClick={handleGenerate}
          disabled={!selectedId || loading}
          className="px-5 py-2 bg-accent text-background font-medium text-sm rounded disabled:opacity-40 hover:bg-accent-dim transition-colors"
        >
          {loading ? "Loading..." : "Generate Dossier"}
        </button>
      </div>
    </div>
  );
}
