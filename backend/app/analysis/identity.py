from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dossier import IdentitySection


async def compute_identity(team_id: int, session: AsyncSession) -> IdentitySection:
    """Compute tactical identity profile for a team.

    Aggregates Match.stats_home / stats_away across all available fixtures to
    produce season-average possession, shots, pass accuracy, fouls, and corners.
    Derives a pressing intensity label (high/medium/low) from fouls + tackles
    proxy. Infers a qualitative play-style label from combined stats.

    Args:
        team_id: Internal DB team ID.
        session: Async SQLAlchemy session.

    Query filter: always apply Match.complete() — five fixtures have no stats
    from the API and must be excluded to keep results consistent.
    """
    # TODO: implement — use .where(Match.complete()) in all DB queries
    raise NotImplementedError
