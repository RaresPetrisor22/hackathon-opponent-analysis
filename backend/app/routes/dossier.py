from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.llm.orchestrator import generate_dossier
from app.mock import build_mock_dossier
from app.models.team import Team
from app.schemas.dossier import DossierResponse

router = APIRouter()

@router.get("/{team_id}", response_model=DossierResponse)
async def get_dossier(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> DossierResponse:
    """Generate and return the full pre-match dossier for the given opponent team."""

    try:
        dossier = await generate_dossier(team_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotImplementedError:
        result = await session.execute(select(Team).where(Team.id == team_id))
        team = result.scalar_one_or_none()
        team_name = team.name if team else f"Team {team_id}"
        return build_mock_dossier(team_id, team_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return dossier
