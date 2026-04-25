from __future__ import annotations

from collections import Counter

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.schemas.dossier import IdentitySection, TacticalIdentityStats


_STAT_KEYS = (
    "ball_possession",
    "total_shots",
    "shots_on_goal",
    "passes_pct",
    "fouls",
    "yellow_cards",
    "corner_kicks",
)


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
    stmt = select(Match).where(
        or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        Match.complete(),
    )
    matches = (await session.execute(stmt)).scalars().all()

    sums: dict[str, float] = {k: 0.0 for k in _STAT_KEYS}
    counts: dict[str, int] = {k: 0 for k in _STAT_KEYS}
    formations: Counter[str] = Counter()

    for m in matches:
        is_home = m.home_team_id == team_id
        stats = m.stats_home if is_home else m.stats_away
        formation = m.formation_home if is_home else m.formation_away
        if not stats:
            continue
        for k in _STAT_KEYS:
            v = stats.get(k)
            if v is None:
                continue
            sums[k] += float(v)
            counts[k] += 1
        if formation:
            formations[formation] += 1

    def avg(k: str) -> float:
        return round(sums[k] / counts[k], 2) if counts[k] else 0.0

    stats = TacticalIdentityStats(
        avg_possession=avg("ball_possession"),
        avg_shots=avg("total_shots"),
        avg_shots_on_target=avg("shots_on_goal"),
        avg_pass_accuracy=avg("passes_pct"),
        avg_fouls=avg("fouls"),
        avg_yellow_cards=avg("yellow_cards"),
        avg_corners=avg("corner_kicks"),
        preferred_formation=formations.most_common(1)[0][0] if formations else "unknown",
    )

    if stats.avg_fouls >= 14.0:
        pressing_intensity = "high"
    elif stats.avg_fouls <= 10.0:
        pressing_intensity = "low"
    else:
        pressing_intensity = "medium"

    if stats.avg_possession >= 55.0 and stats.avg_pass_accuracy >= 80.0:
        play_style = "possession-based build-up"
    elif stats.avg_possession <= 45.0:
        play_style = "direct / counter-attacking"
    elif stats.avg_shots and stats.avg_shots_on_target / stats.avg_shots >= 0.4:
        play_style = "clinical / efficient transitions"
    else:
        play_style = "balanced mid-block"

    notes = (
        f"{play_style.capitalize()} side averaging {stats.avg_possession:.0f}% possession, "
        f"{stats.avg_shots:.1f} shots ({stats.avg_shots_on_target:.1f} on target) and "
        f"{stats.avg_corners:.1f} corners per match. Pressing intensity reads as "
        f"{pressing_intensity} ({stats.avg_fouls:.1f} fouls/match). "
        f"Default shape: {stats.preferred_formation}."
    )

    return IdentitySection(
        stats=stats,
        pressing_intensity=pressing_intensity,
        play_style=play_style,
        notes=notes,
    )
