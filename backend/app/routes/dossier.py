from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.llm.orchestrator import generate_dossier
from app.schemas.dossier import DossierResponse

router = APIRouter()


@router.get("/{team_id}", response_model=DossierResponse)
async def get_dossier(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> DossierResponse:
    """Generate and return the full pre-match dossier for the given opponent team."""
    try:
        return await generate_dossier(team_id, session)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Dossier generation not yet implemented.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
