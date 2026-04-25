from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.team import Team
from app.schemas.dossier import GameStateRecord, GameStateSection


_STATES = ("winning", "drawing", "losing")


async def compute_game_state(team_id: int, session: AsyncSession) -> GameStateSection:
    """Analyse how the team behaves in different game states.

    Walks the per-match goal events to attribute every goal scored and
    conceded to the score-state the team was in immediately before the goal
    (winning / drawing / losing). Aggregates per-state goals_for and
    goals_against averaged across the matches that visited that state, and
    derives qualitative tendency labels by comparing per-state goal rates.

    Note: no coordinate data — behavioural inferences are stat-based only.

    Args:
        team_id: Internal DB team ID.
        session: Async SQLAlchemy session.

    Query filter: always apply Match.complete() — five fixtures have no stats
    from the API and must be excluded to keep results consistent.
    """
    api_team_id = (
        await session.execute(select(Team.api_football_id).where(Team.id == team_id))
    ).scalar_one()

    stmt = select(Match).where(
        or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        Match.complete(),
    )
    matches = (await session.execute(stmt)).scalars().all()

    goals_for = {s: 0 for s in _STATES}
    goals_against = {s: 0 for s in _STATES}
    matches_visiting = {s: 0 for s in _STATES}

    for m in matches:
        events = m.events or []
        goal_events = [e for e in events if e.get("type") == "Goal"]

        def minute(e: dict) -> int:
            t = e.get("time") or {}
            return (t.get("elapsed") or 0) + (t.get("extra") or 0)

        goal_events.sort(key=minute)

        team_score = 0
        opp_score = 0
        visited: set[str] = {"drawing"}  # every match opens 0-0

        for e in goal_events:
            if team_score > opp_score:
                state = "winning"
            elif team_score < opp_score:
                state = "losing"
            else:
                state = "drawing"

            scoring_team = (e.get("team") or {}).get("id")
            own_goal = (e.get("detail") or "") == "Own Goal"

            if scoring_team == api_team_id:
                if own_goal:
                    opp_score += 1
                    goals_against[state] += 1
                else:
                    team_score += 1
                    goals_for[state] += 1
            else:
                if own_goal:
                    team_score += 1
                    goals_for[state] += 1
                else:
                    opp_score += 1
                    goals_against[state] += 1

            if team_score > opp_score:
                visited.add("winning")
            elif team_score < opp_score:
                visited.add("losing")
            else:
                visited.add("drawing")

        for s in visited:
            matches_visiting[s] += 1

    records: list[GameStateRecord] = []
    for s in _STATES:
        n = matches_visiting[s]
        avg_for = round(goals_for[s] / n, 2) if n else 0.0
        avg_against = round(goals_against[s] / n, 2) if n else 0.0

        if s == "winning":
            defensive_change = (
                "tightens up — concedes little" if avg_against < 0.6
                else "vulnerable to equalisers" if avg_against > 1.0
                else "holds shape"
            )
            offensive_change = (
                "keeps pressing for a second" if avg_for > 0.6
                else "manages the lead" if avg_for < 0.3
                else "stays balanced"
            )
        elif s == "losing":
            defensive_change = (
                "leaks further when chasing" if avg_against > 0.8
                else "stays compact while chasing"
            )
            offensive_change = (
                "increases directness, generates chances" if avg_for > 0.8
                else "struggles to create when chasing" if avg_for < 0.4
                else "moderate response when behind"
            )
        else:  # drawing
            defensive_change = (
                "solid in level games" if avg_against < 0.7
                else "concedes the opener too often"
            )
            offensive_change = (
                "breaks deadlock readily" if avg_for > 0.8
                else "slow to break the deadlock" if avg_for < 0.4
                else "patient build from level"
            )

        records.append(
            GameStateRecord(
                state=s,
                matches=n,
                avg_goals_for=avg_for,
                avg_goals_against=avg_against,
                defensive_change=defensive_change,
                offensive_change=offensive_change,
            )
        )

    by_state = {r.state: r for r in records}
    tendency_when_winning = (
        f"In {by_state['winning'].matches} matches led at some point: "
        f"{by_state['winning'].defensive_change}; {by_state['winning'].offensive_change}."
    )
    tendency_when_losing = (
        f"In {by_state['losing'].matches} matches trailed at some point: "
        f"{by_state['losing'].offensive_change}; {by_state['losing'].defensive_change}."
    )

    return GameStateSection(
        records=records,
        tendency_when_losing=tendency_when_losing,
        tendency_when_winning=tendency_when_winning,
    )
