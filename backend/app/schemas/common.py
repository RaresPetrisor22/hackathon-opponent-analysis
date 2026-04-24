from __future__ import annotations

from pydantic import BaseModel


class TeamSummary(BaseModel):
    id: int
    api_football_id: int
    name: str
    short_name: str | None = None
    logo_url: str | None = None


class MatchResult(BaseModel):
    fixture_id: int
    date: str | None
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    venue: str | None = None
