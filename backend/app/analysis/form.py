from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.match import Match
from app.models.team import Team
from app.schemas.dossier import FormSection, MatchFormEntry


async def compute_form(team_id: int, session: AsyncSession, n: int = 10) -> FormSection:
    """Compute recent form for a team.

    Queries the last `n` completed fixtures for `team_id`, ordered by date
    descending. Calculates W/D/L counts, goals scored/conceded averages,
    and returns a FormSection with last_5 and last_10 match entries.

    The form_string is written chronologically (oldest -> newest, left to right).

    Args:
        team_id: Internal DB team ID.
        session: Async SQLAlchemy session.
        n: How many recent matches to fetch (at least 10 for both windows).

    Query filter: always apply Match.complete() — five fixtures have no stats
    from the API and must be excluded to keep results consistent.
    """
    home_alias = aliased(Team)
    away_alias = aliased(Team)

    stmt = (
        select(Match, home_alias.name, away_alias.name)
        .join(home_alias, Match.home_team_id == home_alias.id)
        .join(away_alias, Match.away_team_id == away_alias.id)
        .where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
            Match.complete(),
        )
        .order_by(Match.date.desc())
        .limit(n)
    )

    rows = (await session.execute(stmt)).all()

    entries: list[MatchFormEntry] = []
    for match, home_name, away_name in rows:
        is_home = match.home_team_id == team_id
        if is_home:
            goals_for = match.home_score
            goals_against = match.away_score
            opponent = away_name
            side = "H"
        else:
            goals_for = match.away_score
            goals_against = match.home_score
            opponent = home_name
            side = "A"

        if goals_for > goals_against:
            result = "W"
        elif goals_for < goals_against:
            result = "L"
        else:
            result = "D"

        entries.append(
            MatchFormEntry(
                date=match.date.date().isoformat() if match.date else "",
                opponent=opponent,
                home_away=side,
                goals_for=goals_for,
                goals_against=goals_against,
                result=result,
            )
        )

    last_5 = entries[:5]
    last_10 = entries[:10]

    wins = sum(1 for e in last_5 if e.result == "W")
    draws = sum(1 for e in last_5 if e.result == "D")
    losses = sum(1 for e in last_5 if e.result == "L")

    if last_10:
        goals_scored_avg = round(sum(e.goals_for for e in last_10) / len(last_10), 2)
        goals_conceded_avg = round(sum(e.goals_against for e in last_10) / len(last_10), 2)
    else:
        goals_scored_avg = 0.0
        goals_conceded_avg = 0.0

    # entries are in descending date order; reverse so the string reads
    # chronologically left -> right (oldest -> newest).
    form_string = "".join(e.result for e in reversed(last_5))

    return FormSection(
        last_5=last_5,
        last_10=last_10,
        wins_last5=wins,
        draws_last5=draws,
        losses_last5=losses,
        goals_scored_avg=goals_scored_avg,
        goals_conceded_avg=goals_conceded_avg,
        form_string=form_string,
    )
