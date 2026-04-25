from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.schemas.dossier import PlayerCard, PlayerCardsSection


_MAX_THREATS = 5
_MAX_VULNERABILITIES = 3
_MIN_MATCHES_FOR_VULNERABILITY = 3


def _safe_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


class _PlayerAgg:
    __slots__ = (
        "player_id", "name", "photo", "positions", "numbers",
        "minutes", "matches", "goals", "assists", "shots", "shots_on",
        "yellows", "reds", "fouls_committed", "tackles", "duels_won",
        "duels_total",
    )

    def __init__(self, player_id: int, name: str, photo: str | None) -> None:
        self.player_id = player_id
        self.name = name
        self.photo = photo
        self.positions: Counter[str] = Counter()
        self.numbers: Counter[int] = Counter()
        self.minutes = 0
        self.matches = 0
        self.goals = 0
        self.assists = 0
        self.shots = 0
        self.shots_on = 0
        self.yellows = 0
        self.reds = 0
        self.fouls_committed = 0
        self.tackles = 0
        self.duels_won = 0
        self.duels_total = 0

    def absorb(self, stats: dict[str, Any]) -> None:
        games = stats.get("games") or {}
        minutes = _safe_int(games.get("minutes"))
        if minutes <= 0:
            return  # didn't actually feature
        self.minutes += minutes
        self.matches += 1
        if pos := games.get("position"):
            self.positions[pos] += 1
        if (num := _safe_int(games.get("number"))) > 0:
            self.numbers[num] += 1
        goals = stats.get("goals") or {}
        self.goals += _safe_int(goals.get("total"))
        self.assists += _safe_int(goals.get("assists"))
        shots = stats.get("shots") or {}
        self.shots += _safe_int(shots.get("total"))
        self.shots_on += _safe_int(shots.get("on"))
        cards = stats.get("cards") or {}
        self.yellows += _safe_int(cards.get("yellow"))
        self.reds += _safe_int(cards.get("red"))
        fouls = stats.get("fouls") or {}
        self.fouls_committed += _safe_int(fouls.get("committed"))
        tackles = stats.get("tackles") or {}
        self.tackles += _safe_int(tackles.get("total"))
        duels = stats.get("duels") or {}
        self.duels_total += _safe_int(duels.get("total"))
        self.duels_won += _safe_int(duels.get("won"))

    @property
    def position(self) -> str:
        return self.positions.most_common(1)[0][0] if self.positions else "unknown"

    @property
    def jersey_number(self) -> int | None:
        return self.numbers.most_common(1)[0][0] if self.numbers else None

    @property
    def goal_contributions(self) -> int:
        return self.goals + self.assists

    @property
    def vulnerability_score(self) -> float:
        # Heavier weight on reds, normalised foul rate per 90, plus a small
        # penalty for low duel-success when there's enough sample.
        per90_fouls = (self.fouls_committed * 90.0 / self.minutes) if self.minutes else 0.0
        duel_loss_rate = (
            1 - (self.duels_won / self.duels_total)
            if self.duels_total >= 10
            else 0.0
        )
        return (
            self.yellows * 1.0
            + self.reds * 3.0
            + per90_fouls * 0.5
            + duel_loss_rate * 2.0
        )


async def compute_player_cards(
    team_id: int, session: AsyncSession
) -> PlayerCardsSection:
    """Identify key attacking threats and defensive vulnerabilities.

    For threats: rank players by goals + assists over the season, surface top 5.
    For vulnerabilities: identify positions / players with high cards/fouls
    conceded and low duel-success rates from API-Football fixture player stats.

    Returns at most 5 threat cards and 3 vulnerability cards.

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

    aggs: dict[int, _PlayerAgg] = {}
    for m in matches:
        is_home = m.home_team_id == team_id
        roster = m.players_home if is_home else m.players_away
        if not roster:
            continue
        for entry in roster:
            player = entry.get("player") or {}
            pid = player.get("id")
            if pid is None:
                continue
            agg = aggs.get(pid)
            if agg is None:
                agg = _PlayerAgg(
                    player_id=pid,
                    name=player.get("name") or f"Player {pid}",
                    photo=player.get("photo"),
                )
                aggs[pid] = agg
            for stats in (entry.get("statistics") or []):
                agg.absorb(stats)

    threats = _build_threats(aggs.values())
    vulnerabilities = _build_vulnerabilities(aggs.values())

    return PlayerCardsSection(
        key_threats=threats,
        defensive_vulnerabilities=vulnerabilities,
    )


def _build_threats(aggs) -> list[PlayerCard]:
    all_active = [a for a in aggs if a.matches > 0]
    ranked = sorted(
        all_active,
        key=lambda a: (a.goal_contributions, a.goals, a.minutes),
        reverse=True,
    )
    total_ga = sum(a.goal_contributions for a in all_active)
    high_threshold = max(1, round(total_ga * 0.15))
    medium_threshold = max(1, round(total_ga * 0.07))

    out: list[PlayerCard] = []
    for a in ranked[:_MAX_THREATS]:
        if a.goal_contributions == 0:
            break  # not a real threat
        if a.goal_contributions >= high_threshold:
            level = "high"
        elif a.goal_contributions >= medium_threshold:
            level = "medium"
        else:
            level = "low"
        per90 = round(a.goal_contributions * 90.0 / a.minutes, 2) if a.minutes else 0.0
        out.append(
            PlayerCard(
                player_id=a.player_id,
                name=a.name,
                position=a.position,
                jersey_number=a.jersey_number,
                photo_url=a.photo,
                key_stats={
                    "goals": float(a.goals),
                    "assists": float(a.assists),
                    "shots": float(a.shots),
                    "shots_on_target": float(a.shots_on),
                    "matches": float(a.matches),
                    "minutes": float(a.minutes),
                    "g_a_per_90": per90,
                },
                threat_level=level,
                notes=(
                    f"{a.goals} goals + {a.assists} assists in {a.matches} apps "
                    f"({per90:.2f} G+A per 90). Position: {a.position}."
                ),
            )
        )
    return out


def _build_vulnerabilities(aggs) -> list[PlayerCard]:
    eligible = [a for a in aggs if a.matches >= _MIN_MATCHES_FOR_VULNERABILITY]
    ranked = sorted(eligible, key=lambda a: a.vulnerability_score, reverse=True)
    out: list[PlayerCard] = []
    for a in ranked[:_MAX_VULNERABILITIES]:
        if a.vulnerability_score <= 0:
            break
        yellows_per_game = a.yellows / a.matches if a.matches else 0.0
        if a.reds > 0 or yellows_per_game >= 0.20:
            level = "high"
        elif yellows_per_game >= 0.12:
            level = "medium"
        else:
            level = "low"
        per90_fouls = round(a.fouls_committed * 90.0 / a.minutes, 2) if a.minutes else 0.0
        duel_pct = (
            round(a.duels_won * 100 / a.duels_total, 1)
            if a.duels_total else 0.0
        )
        out.append(
            PlayerCard(
                player_id=a.player_id,
                name=a.name,
                position=a.position,
                jersey_number=a.jersey_number,
                photo_url=a.photo,
                key_stats={
                    "yellow_cards": float(a.yellows),
                    "red_cards": float(a.reds),
                    "fouls_committed": float(a.fouls_committed),
                    "fouls_per_90": per90_fouls,
                    "duels_won_pct": duel_pct,
                    "matches": float(a.matches),
                },
                threat_level=level,
                notes=(
                    f"{a.yellows}Y / {a.reds}R, {per90_fouls:.1f} fouls per 90 "
                    f"over {a.matches} apps. Position: {a.position}."
                ),
            )
        )
    return out
