from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.player import Player
from app.models.team import Team
from app.schemas.common import PlayerSummary, TeamSummary

router = APIRouter()


# Position-group ordering used for roster sorting (Goalkeeper -> Defender -> Midfielder -> Attacker -> other)
_POSITION_ORDER = {
    "Goalkeeper": 1,
    "Defender": 2,
    "Midfielder": 3,
    "Attacker": 4,
}


@router.get("", response_model=list[TeamSummary])
async def list_teams(session: AsyncSession = Depends(get_session)) -> list[TeamSummary]:
    """Return all teams in the DB (SuperLiga + FCU)."""
    result = await session.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()
    return [
        TeamSummary(
            id=t.id,
            api_football_id=t.api_football_id,
            name=t.name,
            short_name=t.short_name,
            logo_url=t.logo_url,
        )
        for t in teams
    ]


@router.get("/{team_id}/players", response_model=list[PlayerSummary])
async def list_team_players(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[PlayerSummary]:
    """Return all players belonging to the given team, sorted by position group then jersey number."""
    team = (
        await session.execute(select(Team).where(Team.id == team_id))
    ).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

    result = await session.execute(
        select(Player).where(Player.team_id == team_id)
    )
    players = result.scalars().all()

    def _sort_key(p: Player) -> tuple[int, int, str]:
        pos_rank = _POSITION_ORDER.get(p.position or "", 99)
        jersey = p.jersey_number if p.jersey_number is not None else 999
        return (pos_rank, jersey, p.name)

    players_sorted = sorted(players, key=_sort_key)

    return [
        PlayerSummary(
            id=p.id,
            api_football_id=p.api_football_id,
            name=p.name,
            position=p.position,
            jersey_number=p.jersey_number,
            nationality=p.nationality,
            age=p.age,
            photo_url=p.photo_url,
        )
        for p in players_sorted
    ]
