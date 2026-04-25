// TypeScript types mirroring backend/app/schemas/dossier.py and common.py
// Keep in sync with Pydantic models.

export interface TeamSummary {
  id: number;
  api_football_id: number;
  name: string;
  short_name: string | null;
  logo_url: string | null;
}

// --- Form ---

export interface MatchFormEntry {
  date: string;
  opponent: string;
  home_away: "H" | "A";
  goals_for: number;
  goals_against: number;
  result: "W" | "D" | "L";
}

export interface FormSection {
  last_5: MatchFormEntry[];
  last_10: MatchFormEntry[];
  wins_last5: number;
  draws_last5: number;
  losses_last5: number;
  goals_scored_avg: number;
  goals_conceded_avg: number;
  form_string: string;
}

// --- Identity ---

export interface TacticalIdentityStats {
  avg_possession: number;
  avg_shots: number;
  avg_shots_on_target: number;
  avg_pass_accuracy: number;
  avg_fouls: number;
  avg_yellow_cards: number;
  avg_corners: number;
  preferred_formation: string;
}

export interface IdentitySection {
  stats: TacticalIdentityStats;
  pressing_intensity: "high" | "medium" | "low";
  play_style: string;
  notes: string;
}

// --- Matchups ---

export interface ArchetypeRecord {
  archetype_id: number;
  archetype_name: string;
  archetype_description: string;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  xg_diff: number | null;
}

export interface MatchupSection {
  archetypes: ArchetypeRecord[];
  fcu_archetype_id: number;
  fcu_archetype_name: string;
  prediction_summary: string;
  best_archetype_vs_opponent: string;
  fcu_tactical_profile: TacticalIdentityStats | null;
}

// --- Players ---

export interface PlayerCard {
  player_id: number;
  name: string;
  position: string;
  jersey_number: number | null;
  photo_url: string | null;
  key_stats: Record<string, number>;
  threat_level: "high" | "medium" | "low";
  notes: string;
}

export interface PlayerCardsSection {
  key_threats: PlayerCard[];
  defensive_vulnerabilities: PlayerCard[];
}

// --- Game State ---

export interface GameStateRecord {
  state: "winning" | "drawing" | "losing";
  matches: number;
  avg_goals_for: number;
  avg_goals_against: number;
  defensive_change: string;
  offensive_change: string;
}

export interface GameStateSection {
  records: GameStateRecord[];
  tendency_when_losing: string;
  tendency_when_winning: string;
}

// --- Referee ---

export interface RefereeSection {
  referee_name: string | null;
  total_matches: number;
  avg_yellow_cards: number;
  avg_red_cards: number;
  avg_fouls_called: number;
  home_advantage_factor: number | null;
  notes: string;
}

// --- Gameplan ---

export interface GameplanNarrative {
  headline: string;
  body: string;
  key_actions: string[];
}

// --- Top-level ---

export interface DossierResponse {
  opponent_id: number;
  opponent_name: string;
  generated_at: string;
  form: FormSection;
  identity: IdentitySection;
  matchups: MatchupSection;
  players: PlayerCardsSection;
  game_state: GameStateSection;
  referee: RefereeSection;
  gameplan: GameplanNarrative;
}
