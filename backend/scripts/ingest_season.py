"""ingest_season.py — Pull SuperLiga season data from API-Football.

Usage:
    cd backend
    uv run python scripts/ingest_season.py              # full ingest
    uv run python scripts/ingest_season.py --no-stats   # only teams + fixture skeletons
    uv run python scripts/ingest_season.py --limit 20   # only first 20 FT fixtures (for testing)

What it does:
1. Fetches all SuperLiga teams and upserts them to the DB.
2. Fetches all fixtures for the season and upserts Match skeletons.
3. For each completed (FT) fixture, fetches /fixtures/statistics, /fixtures/lineups,
   /fixtures/events, and /fixtures/players, then fills all Match columns.

All raw responses are cached to disk (see ApiFootballClient). Re-running the script
uses the cache and makes zero new API calls.

Pro plan budget: 7500 req/day, 300 req/min.
    1 (leagues) + 1 (teams) + 1 (fixtures) + 4*N (stats + lineups + events + players)
SuperLiga has ~315 FT matches; roughly 1263 requests, completing in ~5 minutes.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Force UTF-8 stdout so Romanian team names print on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Allow running from scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import AsyncSessionLocal, init_db
from app.ingestion.api_football import (
    ApiFootballClient,
    extract_formation,
    normalize_statistics,
)
from app.models.player import Player
from app.ingestion.upserts import (
    MIN_FIXTURES_FOR_LEAGUE_MEMBERSHIP,
    count_team_appearances,  # noqa: F401  (re-exported for backwards compat)
    select_league_teams,
    upsert_match_skeleton,
    upsert_team,
)
from app.models.match import Match
from app.models.team import Team

console = Console()


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

async def ingest_teams(
    client: ApiFootballClient,
    session: AsyncSession,
    league_team_ids: set[int] | None = None,
) -> dict[int, int]:
    """Fetch and upsert teams. Returns mapping {api_football_id: internal_id}.

    If league_team_ids is provided, only teams whose API-Football ID is in that
    set will be upserted (used to filter out Liga II playoff outsiders).
    """
    teams_data = await client.get_teams(
        settings.superliga_league_id, settings.superliga_season
    )
    team_map: dict[int, int] = {}
    skipped = 0

    for entry in teams_data.get("response", []):
        api_id = entry["team"]["id"]
        if league_team_ids is not None and api_id not in league_team_ids:
            skipped += 1
            continue
        team = await upsert_team(session, entry["team"])
        team_map[team.api_football_id] = team.id

    await session.commit()
    msg = f"Upserted {len(team_map)} teams."
    if skipped:
        msg += f" (skipped {skipped} non-league teams)"
    console.print(f"[green]{msg}[/green]")
    return team_map


async def ingest_fixtures(
    client: ApiFootballClient,
    session: AsyncSession,
    team_id_map: dict[int, int],
) -> list[dict[str, Any]]:
    """Fetch and upsert all fixture skeletons. Returns the raw fixture list."""
    fixtures_data = await client.get_fixtures(
        settings.superliga_league_id, settings.superliga_season
    )
    fixtures = fixtures_data.get("response", [])

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Upserting fixtures"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("fixtures", total=len(fixtures))
        for fixture in fixtures:
            await upsert_match_skeleton(session, fixture, team_id_map)
            progress.advance(task)

    await session.commit()
    console.print(f"[green]Upserted {len(fixtures)} fixture skeletons.[/green]")
    return fixtures


async def ingest_fixture_details(
    client: ApiFootballClient,
    session: AsyncSession,
    fixtures: list[dict[str, Any]],
    team_id_map: dict[int, int],
    limit: int | None = None,
) -> None:
    """For each FT fixture, fetch statistics, lineups, events, and player stats."""
    completed = [
        f for f in fixtures
        if (f.get("fixture") or {}).get("status", {}).get("short") == "FT"
    ]
    if limit:
        completed = completed[:limit]

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Fetching fixture details"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("details", total=len(completed))

        for fixture in completed:
            fid = fixture["fixture"]["id"]
            home_api_id = fixture["teams"]["home"]["id"]
            away_api_id = fixture["teams"]["away"]["id"]

            try:
                stats_resp = await client.get_fixture_statistics(fid)
                lineups_resp = await client.get_fixture_lineups(fid)
                events_resp = await client.get_fixture_events(fid)
                players_resp = await client.get_fixture_players(fid)
            except Exception as exc:
                console.print(f"[yellow]Fixture {fid} fetch failed: {exc}[/yellow]")
                progress.advance(task)
                continue

            match = await session.get(Match, fid)
            if match is None:
                progress.advance(task)
                continue

            # Statistics
            for entry in stats_resp.get("response", []):
                team_api_id = entry.get("team", {}).get("id")
                normalised = normalize_statistics(entry.get("statistics", []))
                if team_api_id == home_api_id:
                    match.stats_home = normalised
                elif team_api_id == away_api_id:
                    match.stats_away = normalised

            # Lineups / formations
            lineup_list = lineups_resp.get("response", [])
            match.formation_home = extract_formation(lineup_list, home_api_id)
            match.formation_away = extract_formation(lineup_list, away_api_id)

            # Events (goals, cards, subs with elapsed minute)
            match.events = events_resp.get("response", [])

            # Player stats — split by team side
            home_players: list[dict[str, Any]] = []
            away_players: list[dict[str, Any]] = []
            for team_entry in players_resp.get("response", []):
                tid = team_entry.get("team", {}).get("id")
                player_list = team_entry.get("players", [])
                if tid == home_api_id:
                    home_players = player_list
                elif tid == away_api_id:
                    away_players = player_list

            match.players_home = home_players
            match.players_away = away_players

            # Upsert player rows from lineup data (basic identity only)
            for side_api_id, side_players in (
                (home_api_id, home_players),
                (away_api_id, away_players),
            ):
                internal_team_id = team_id_map.get(side_api_id)
                if internal_team_id is None:
                    continue
                for p in side_players:
                    info = p.get("player", {})
                    api_pid = info.get("id")
                    if not api_pid:
                        continue
                    existing = (
                        await session.execute(
                            select(Player).where(Player.api_football_id == api_pid)
                        )
                    ).scalar_one_or_none()
                    if existing is None:
                        session.add(
                            Player(
                                api_football_id=api_pid,
                                team_id=internal_team_id,
                                name=info.get("name", ""),
                                position=info.get("pos"),
                                photo_url=info.get("photo"),
                            )
                        )

            progress.advance(task)

        await session.commit()

    console.print(f"[green]Updated details for {len(completed)} fixtures.[/green]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace) -> None:
    if not settings.api_football_key:
        console.print("[red]API_FOOTBALL_KEY is not set in .env — aborting.[/red]")
        return

    await init_db()
    client = ApiFootballClient()

    # Confirm the league id
    leagues = await client.get_leagues(country="Romania")
    league_ids = [
        entry["league"]["id"]
        for entry in leagues.get("response", [])
        if "league" in entry
    ]
    console.print(
        f"Romania leagues available: {league_ids}. "
        f"Using league_id={settings.superliga_league_id}, season={settings.superliga_season}."
    )

    async with AsyncSessionLocal() as session:
        # Step 1: fetch fixtures first (raw — just to count team appearances)
        fixtures_data = await client.get_fixtures(
            settings.superliga_league_id, settings.superliga_season
        )
        raw_fixtures = fixtures_data.get("response", [])
        league_team_ids = select_league_teams(raw_fixtures)
        console.print(
            f"Detected {len(league_team_ids)} league teams "
            f"(teams with >= {MIN_FIXTURES_FOR_LEAGUE_MEMBERSHIP} fixtures)."
        )

        # Step 2: upsert teams, filtered to real league participants
        team_id_map = await ingest_teams(client, session, league_team_ids=league_team_ids)

        stmt = select(Team).order_by(Team.name)
        all_teams = (await session.execute(stmt)).scalars().all()
        for t in all_teams:
            console.print(f"  api_id={t.api_football_id:>5}  {t.name}")

        # Step 3: upsert match skeletons (fixtures with non-league teams are skipped)
        fixtures = await ingest_fixtures(client, session, team_id_map)

        if not args.no_stats:
            await ingest_fixture_details(client, session, fixtures, team_id_map, limit=args.limit)

    console.print("[bold green]Ingestion complete.[/bold green]")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--no-stats",
        action="store_true",
        help="Only ingest teams + fixture skeletons; skip the per-fixture stats calls.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only fetch stats for the first N completed fixtures (for testing).",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
