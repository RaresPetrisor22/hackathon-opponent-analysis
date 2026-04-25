"""ingest_standings_h2h.py — Fetch league standings and FCU head-to-head records.

Usage:
    cd backend
    uv run python scripts/ingest_standings_h2h.py

What it does:
1. Fetches /standings for SuperLiga 2024-25 and upserts one Standing row per team.
2. Fetches /fixtures/headtohead for FCU vs every other league team (15 calls)
   and caches responses to disk — the matchup analysis module reads from cache.

All responses are disk-cached; re-running makes zero new API calls.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
from app.ingestion.api_football import ApiFootballClient
from app.models.standings import Standing
from app.models.team import Team

console = Console()


async def ingest_standings(client: ApiFootballClient, session: AsyncSession) -> None:
    data = await client.get_standings(settings.superliga_league_id, settings.superliga_season)

    league_block = data.get("response", [{}])[0].get("league", {})
    # SuperLiga has 3 standing groups: championship playoff, relegation playoff,
    # and regular season. Flatten all groups; teams appear in multiple groups
    # (regular season + playoff) — last write wins, so playoff rows (most recent) take priority.
    all_groups = league_block.get("standings", [])
    rows = [entry for group in reversed(all_groups) for entry in group]

    upserted = 0
    skipped = 0
    for entry in rows:
        api_team_id = entry["team"]["id"]

        result = await session.execute(
            select(Team).where(Team.api_football_id == api_team_id)
        )
        team = result.scalar_one_or_none()
        if team is None:
            skipped += 1
            continue

        existing = (
            await session.execute(
                select(Standing).where(
                    Standing.team_id == team.id,
                    Standing.season == settings.superliga_season,
                    Standing.league_id == settings.superliga_league_id,
                )
            )
        ).scalar_one_or_none()

        all_stats = entry.get("all", {})
        goals = all_stats.get("goals", {})

        values = dict(
            rank=entry["rank"],
            points=entry["points"],
            played=all_stats.get("played", 0),
            wins=all_stats.get("win", 0),
            draws=all_stats.get("draw", 0),
            losses=all_stats.get("lose", 0),
            goals_for=goals.get("for", 0),
            goals_against=goals.get("against", 0),
            goal_diff=entry.get("goalsDiff", 0),
            form=entry.get("form"),
            description=entry.get("description"),
        )

        if existing is None:
            session.add(
                Standing(
                    team_id=team.id,
                    season=settings.superliga_season,
                    league_id=settings.superliga_league_id,
                    **values,
                )
            )
        else:
            for k, v in values.items():
                setattr(existing, k, v)

        upserted += 1

    await session.commit()
    console.print(f"[green]Upserted {upserted} standings rows. (skipped {skipped} unknown teams)[/green]")


async def ingest_h2h(client: ApiFootballClient, session: AsyncSession) -> None:
    result = await session.execute(
        select(Team).where(Team.api_football_id != settings.fcu_team_id)
    )
    opponents = result.scalars().all()

    console.print(f"Fetching H2H: FCU vs {len(opponents)} opponents...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]H2H"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("h2h", total=len(opponents))
        for opp in opponents:
            try:
                await client.get_head_to_head(settings.fcu_team_id, opp.api_football_id)
            except Exception as exc:
                console.print(f"[yellow]H2H vs {opp.name} failed: {exc}[/yellow]")
            progress.advance(task)

    console.print("[green]H2H cache populated.[/green]")


async def main() -> None:
    if not settings.api_football_key:
        console.print("[red]API_FOOTBALL_KEY not set — aborting.[/red]")
        return

    await init_db()
    client = ApiFootballClient()

    async with AsyncSessionLocal() as session:
        console.print("Fetching standings...")
        await ingest_standings(client, session)

        await ingest_h2h(client, session)

    console.print("[bold green]Done.[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
