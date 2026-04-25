from __future__ import annotations

from pydantic import BaseModel


# --- Form & Momentum ---

class MatchFormEntry(BaseModel):
    date: str
    opponent: str
    home_away: str  # "H" | "A"
    goals_for: int
    goals_against: int
    result: str  # "W" | "D" | "L"


class FormSection(BaseModel):
    last_5: list[MatchFormEntry]
    last_10: list[MatchFormEntry]
    wins_last5: int
    draws_last5: int
    losses_last5: int
    goals_scored_avg: float
    goals_conceded_avg: float
    form_string: str  # e.g. "WWDLW"


# --- Tactical Identity ---

class TacticalIdentityStats(BaseModel):
    avg_possession: float
    avg_shots: float
    avg_shots_on_target: float
    avg_pass_accuracy: float
    avg_fouls: float
    avg_yellow_cards: float
    avg_corners: float
    preferred_formation: str


class IdentitySection(BaseModel):
    stats: TacticalIdentityStats
    pressing_intensity: str  # "high" | "medium" | "low"
    play_style: str          # human label derived from stats
    notes: str


# --- Matchup Intelligence (hero feature) ---

class ArchetypeRecord(BaseModel):
    archetype_id: int
    archetype_name: str
    archetype_description: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: float
    goals_against: float
    xg_diff: float | None = None


class MatchupSection(BaseModel):
    archetypes: list[ArchetypeRecord]
    fcu_archetype_id: int
    fcu_archetype_name: str
    prediction_summary: str
    best_archetype_vs_opponent: str
    fcu_tactical_profile: TacticalIdentityStats | None = None


# --- Player Threat & Vulnerability Cards ---

class PlayerCard(BaseModel):
    player_id: int
    name: str
    position: str
    jersey_number: int | None
    photo_url: str | None
    key_stats: dict[str, float]
    threat_level: str   # "high" | "medium" | "low"
    notes: str


class PlayerCardsSection(BaseModel):
    key_threats: list[PlayerCard]
    defensive_vulnerabilities: list[PlayerCard]


# --- Game State Intelligence ---

class GameStateRecord(BaseModel):
    state: str  # "winning" | "drawing" | "losing"
    matches: int
    avg_goals_for: float
    avg_goals_against: float
    defensive_change: str   # qualitative label
    offensive_change: str


class GameStateSection(BaseModel):
    records: list[GameStateRecord]
    tendency_when_losing: str
    tendency_when_winning: str


# --- Referee Context ---

class RefereeSection(BaseModel):
    referee_name: str | None
    total_matches: int
    avg_yellow_cards: float
    avg_red_cards: float
    avg_fouls_called: float
    home_advantage_factor: float | None
    notes: str


# --- Gameplan Narrative (LLM) ---

class GameplanNarrative(BaseModel):
    headline: str
    body: str           # markdown-formatted multi-paragraph narrative
    key_actions: list[str]  # bullet points for the coaching whiteboard


# --- Top-level DossierResponse ---

class DossierResponse(BaseModel):
    opponent_id: int
    opponent_name: str
    generated_at: str   # ISO datetime

    form: FormSection
    identity: IdentitySection
    matchups: MatchupSection
    players: PlayerCardsSection
    game_state: GameStateSection
    referee: RefereeSection
    gameplan: GameplanNarrative
