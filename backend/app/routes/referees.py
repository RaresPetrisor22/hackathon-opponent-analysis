from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.referee import compute_referee_context
from app.config import settings
from app.db import get_session
from app.models.match import Match
from app.schemas.dossier import RefereeSection

router = APIRouter()


@router.get("", response_model=list[str])
async def list_referees(
    session: AsyncSession = Depends(get_session),
) -> list[str]:
    """Return all distinct referee names from completed SuperLiga matches."""
    stmt = (
        select(distinct(Match.referee_name))
        .where(
            Match.league_id == settings.superliga_league_id,
            Match.season_id == settings.superliga_season,
            Match.referee_name.is_not(None),
            Match.complete(),
        )
        .order_by(Match.referee_name)
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


@router.get("/stats", response_model=RefereeSection)
async def get_referee_stats(
    name: str = Query(..., description="Referee full name"),
    session: AsyncSession = Depends(get_session),
) -> RefereeSection:
    """Return statistical profile for a named referee."""
    return await compute_referee_context(
        name,
        settings.superliga_league_id,
        settings.superliga_season,
        session,
    )
