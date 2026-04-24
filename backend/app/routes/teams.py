from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.team import Team
from app.schemas.common import TeamSummary

router = APIRouter()


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
