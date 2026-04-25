from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.schemas.dossier import RefereeSection


def _empty(referee_name: str | None, note: str) -> RefereeSection:
    return RefereeSection(
        referee_name=referee_name,
        total_matches=0,
        avg_yellow_cards=0.0,
        avg_red_cards=0.0,
        avg_fouls_called=0.0,
        home_advantage_factor=None,
        notes=note,
    )


def _sum_stat(stats: dict | None, key: str) -> float:
    if not stats:
        return 0.0
    v = stats.get(key)
    return float(v) if v is not None else 0.0


async def compute_referee_context(
    referee_name: str | None,
    league_id: int,
    season: int,
    session: AsyncSession,
) -> RefereeSection:
    """Compute statistical profile for the assigned referee.

    Queries all fixtures in the season officiated by the named referee.
    Aggregates avg yellow cards, red cards, fouls called per match.
    Computes a rough home-advantage factor (home win % in their fixtures vs
    league average). Returns RefereeSection; if referee_name is None, returns
    a section with null/zero values and a note.

    Args:
        referee_name: Full name as returned by API-Football (may be None if unassigned).
        league_id: API-Football league ID.
        season: Season year.
        session: Async SQLAlchemy session.

    Query filter: always apply Match.complete() — five fixtures have no stats
    from the API and must be excluded to keep results consistent.
    """
    if not referee_name:
        return _empty(None, "No referee assigned yet for the upcoming fixture.")

    stmt = select(Match).where(
        Match.referee_name == referee_name,
        Match.league_id == league_id,
        Match.season_id == season,
        Match.complete(),
    )
    matches = (await session.execute(stmt)).scalars().all()

    if not matches:
        return _empty(
            referee_name,
            f"No prior matches recorded for {referee_name} in this season.",
        )

    n = len(matches)
    total_yellows = 0.0
    total_reds = 0.0
    total_fouls = 0.0
    home_wins = 0

    for m in matches:
        for stats in (m.stats_home, m.stats_away):
            total_yellows += _sum_stat(stats, "yellow_cards")
            total_reds += _sum_stat(stats, "red_cards")
            total_fouls += _sum_stat(stats, "fouls")
        if (
            m.home_score is not None
            and m.away_score is not None
            and m.home_score > m.away_score
        ):
            home_wins += 1

    avg_yellows = round(total_yellows / n, 2)
    avg_reds = round(total_reds / n, 2)
    avg_fouls = round(total_fouls / n, 2)
    home_advantage = round(home_wins / n, 3)

    if avg_yellows >= 5.0:
        card_label = "card-heavy"
    elif avg_yellows <= 3.0:
        card_label = "lenient with cards"
    else:
        card_label = "average card rate"

    notes = (
        f"{referee_name} has officiated {n} matches this season ({card_label}: "
        f"{avg_yellows:.1f} yellows, {avg_reds:.2f} reds, {avg_fouls:.1f} fouls "
        f"per match). Home win rate under this referee: {home_advantage:.0%}."
    )

    return RefereeSection(
        referee_name=referee_name,
        total_matches=n,
        avg_yellow_cards=avg_yellows,
        avg_red_cards=avg_reds,
        avg_fouls_called=avg_fouls,
        home_advantage_factor=home_advantage,
        notes=notes,
    )
