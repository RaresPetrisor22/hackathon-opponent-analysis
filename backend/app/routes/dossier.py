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

_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "dossier_cache"
_CACHE_TTL = timedelta(hours=24)


def _cache_path(team_id: int) -> Path:
    return _CACHE_DIR / f"{team_id}.json"


def _read_cache(team_id: int) -> DossierResponse | None:
    path = _cache_path(team_id)
    if not path.exists():
        return None
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc
    )
    if age > _CACHE_TTL:
        return None
    return DossierResponse.model_validate_json(path.read_text())


def _write_cache(team_id: int, dossier: DossierResponse) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(team_id).write_text(dossier.model_dump_json())


@router.get("/{team_id}", response_model=DossierResponse)
async def get_dossier(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> DossierResponse:
    """Generate and return the full pre-match dossier for the given opponent team."""
    cached = _read_cache(team_id)
    if cached is not None:
        return cached

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

    _write_cache(team_id, dossier)
    return dossier
