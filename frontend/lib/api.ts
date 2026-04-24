import type { DossierResponse, TeamSummary } from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchTeams(): Promise<TeamSummary[]> {
  return apiFetch<TeamSummary[]>("/teams");
}

export async function fetchDossier(teamId: number): Promise<DossierResponse> {
  return apiFetch<DossierResponse>(`/dossier/${teamId}`);
}
