"""Database upsert helpers used by the ingest scripts.

Kept in a separate module (not in scripts/) so they can be unit-tested without
importing the CLI script. Pure SQLAlchemy — no rich/console dependencies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.team import Team

# Minimum fixtures required for a team to count as a true league participant.
# API-Football includes relegation/promotion playoff opponents from Liga II under
# the same league_id; those teams only appear in 2-4 playoff fixtures and should
# be filtered out of the dossier.
MIN_FIXTURES_FOR_LEAGUE_MEMBERSHIP = 10


async def upsert_team(session: AsyncSession, team_data: dict[str, Any]) -> Team:
    """Insert or update a Team row keyed by api_football_id."""
    api_id = team_data["id"]
    stmt = select(Team).where(Team.api_football_id == api_id)
    team = (await session.execute(stmt)).scalar_one_or_none()

    if team is None:
        team = Team(
            api_football_id=api_id,
            name=team_data.get("name", f"team_{api_id}"),
            short_name=team_data.get("code"),
            logo_url=team_data.get("logo"),
            country=team_data.get("country"),
        )
        session.add(team)
    else:
        team.name = team_data.get("name", team.name)
        team.short_name = team_data.get("code", team.short_name)
        team.logo_url = team_data.get("logo", team.logo_url)
        team.country = team_data.get("country", team.country)

    await session.flush()
    return team


async def get_team_internal_id(session: AsyncSession, api_football_id: int) -> int | None:
    """Look up internal Team.id by API-Football team id."""
    stmt = select(Team.id).where(Team.api_football_id == api_football_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_match_skeleton(
    session: AsyncSession,
    fixture: dict[str, Any],
    team_id_map: dict[int, int],
) -> Match | None:
    """Insert or update a Match row from a /fixtures payload (no stats yet).

    Returns None if either team is not in team_id_map (Liga II playoff outsider).
    """
    fx = fixture["fixture"]
    teams = fixture["teams"]
    goals = fixture["goals"]
    league = fixture["league"]

    fixture_id = fx["id"]
    home_api_id = teams["home"]["id"]
    away_api_id = teams["away"]["id"]

    home_internal = team_id_map.get(home_api_id)
    away_internal = team_id_map.get(away_api_id)
    if home_internal is None or away_internal is None:
        return None

    date_str = fx.get("date")
    match_date = datetime.fromisoformat(date_str) if date_str else None

    existing = await session.get(Match, fixture_id)
    if existing is None:
        match = Match(
            id=fixture_id,
            season_id=league["season"],
            league_id=league["id"],
            home_team_id=home_internal,
            away_team_id=away_internal,
            home_score=goals.get("home"),
            away_score=goals.get("away"),
            date=match_date,
            venue=(fx.get("venue") or {}).get("name"),
            referee_name=fx.get("referee"),
            status=(fx.get("status") or {}).get("short"),
        )
        session.add(match)
    else:
        existing.home_score = goals.get("home")
        existing.away_score = goals.get("away")
        existing.date = match_date
        existing.venue = (fx.get("venue") or {}).get("name")
        existing.referee_name = fx.get("referee")
        existing.status = (fx.get("status") or {}).get("short")
        match = existing

    await session.flush()
    return match


def count_team_appearances(fixtures: list[dict[str, Any]]) -> dict[int, int]:
    """Count how many fixtures each team appears in (home or away)."""
    counts: dict[int, int] = {}
    for f in fixtures:
        for side in ("home", "away"):
            tid = f["teams"][side]["id"]
            counts[tid] = counts.get(tid, 0) + 1
    return counts


def select_league_teams(
    fixtures: list[dict[str, Any]],
    min_fixtures: int = MIN_FIXTURES_FOR_LEAGUE_MEMBERSHIP,
) -> set[int]:
    """Return set of team IDs that appear in at least min_fixtures fixtures."""
    counts = count_team_appearances(fixtures)
    return {tid for tid, n in counts.items() if n >= min_fixtures}
