"""ingest_season.py — Pull SuperLiga 2024-25 data from API-Football.

Usage:
    cd backend
    uv run python scripts/ingest_season.py

What it does:
1. Fetches all SuperLiga teams and upserts them to the DB.
2. Fetches all fixtures for the season.
3. For each completed fixture, fetches statistics and player stats.
4. All raw responses are cached to disk first (see ApiFootballClient).

Free tier: 100 req/day. This script will use roughly:
  1 (leagues) + 1 (teams) + 1 (fixtures) + 2*N (stats + players per fixture) requests.
  For ~30 SuperLiga rounds * 8 matches = ~480 fixture requests.
  Run over multiple days if on free tier, or buy a paid plan for hackathon week.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running from scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from app.config import settings
from app.db import AsyncSessionLocal, init_db
from app.ingestion.api_football import ApiFootballClient

console = Console()


async def main() -> None:
    await init_db()
    client = ApiFootballClient()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        # Step 1: fetch leagues and confirm SuperLiga ID
        task = progress.add_task("Fetching Romanian leagues...", total=None)
        leagues = await client.get_leagues(country="Romania")
        progress.update(task, completed=True)
        console.print(f"League response: {len(leagues.get('response', []))} leagues found.")
        console.print(
            f"Using SuperLiga league_id={settings.superliga_league_id} "
            f"season={settings.superliga_season}. Confirm this is correct above."
        )

        # Step 2: fetch teams
        task = progress.add_task("Fetching teams...", total=None)
        teams_data = await client.get_teams(settings.superliga_league_id, settings.superliga_season)
        progress.update(task, completed=True)
        # TODO: upsert teams to DB

        # Step 3: fetch all fixtures
        task = progress.add_task("Fetching fixtures...", total=None)
        fixtures_data = await client.get_fixtures(
            settings.superliga_league_id, settings.superliga_season
        )
        fixtures = fixtures_data.get("response", [])
        progress.update(task, completed=True)
        console.print(f"{len(fixtures)} fixtures found.")

        # Step 4: fetch stats per completed fixture
        completed = [
            f for f in fixtures if f.get("fixture", {}).get("status", {}).get("short") == "FT"
        ]
        task = progress.add_task(f"Fetching stats for {len(completed)} completed fixtures...", total=len(completed))

        async with AsyncSessionLocal() as session:
            for fixture in completed:
                fid = fixture["fixture"]["id"]
                await client.get_fixture_statistics(fid)
                await client.get_fixture_players(fid)
                # TODO: parse and upsert Match, stats_home, stats_away to DB
                progress.advance(task)

    console.print("[green]Ingestion complete.[/green]")


if __name__ == "__main__":
    asyncio.run(main())
