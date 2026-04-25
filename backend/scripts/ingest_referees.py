"""ingest_referees.py — Build referee profiles from existing match data.

Usage:
    cd backend
    uv run python scripts/ingest_referees.py

What it does:
1. Aggregates yellow cards, red cards, fouls, and home win rate per referee
   directly from the matches table (no new API calls needed — all stats are
   already stored in Match.stats_home / stats_away).
2. Upserts one RefereeProfile row per referee.
3. Pre-caches /fixtures?referee=... for all 29 referees (29 API calls) so
   the referee analysis module can optionally call the client at zero cost.

Only matches passing Match.complete() are used to keep stats consistent.
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
from app.models.match import Match
from app.models.referee import RefereeProfile

console = Console()


async def build_referee_profiles(session: AsyncSession) -> None:
    result = await session.execute(
        select(Match).where(Match.complete())
    )
    matches = result.scalars().all()

    # Aggregate per referee
    stats: dict[str, dict] = {}
    for m in matches:
        ref = m.referee_name
        if not ref:
            continue
        if ref not in stats:
            stats[ref] = {
                "total": 0,
                "yellows": 0.0,
                "reds": 0.0,
                "fouls": 0.0,
                "home_wins": 0,
            }
        s = stats[ref]
        s["total"] += 1

        sh = m.stats_home or {}
        sa = m.stats_away or {}
        s["yellows"] += (sh.get("yellow_cards") or 0) + (sa.get("yellow_cards") or 0)
        s["reds"] += (sh.get("red_cards") or 0) + (sa.get("red_cards") or 0)
        s["fouls"] += (sh.get("fouls") or 0) + (sa.get("fouls") or 0)

        if m.home_score is not None and m.away_score is not None:
            if m.home_score > m.away_score:
                s["home_wins"] += 1

    # League-wide home win % (denominator for home_advantage_factor)
    total_matches = len(matches)
    total_home_wins = sum(
        1 for m in matches
        if m.home_score is not None and m.away_score is not None and m.home_score > m.away_score
    )
    league_home_win_pct = total_home_wins / total_matches if total_matches else 0.5

    upserted = 0
    for name, s in stats.items():
        n = s["total"]
        home_win_pct = s["home_wins"] / n if n else 0.0
        home_advantage_factor = (
            home_win_pct / league_home_win_pct if league_home_win_pct else 1.0
        )

        existing = (
            await session.execute(
                select(RefereeProfile).where(RefereeProfile.name == name)
            )
        ).scalar_one_or_none()

        values = dict(
            total_matches=n,
            avg_yellow_cards=round(s["yellows"] / n, 3),
            avg_red_cards=round(s["reds"] / n, 3),
            avg_fouls=round(s["fouls"] / n, 3),
            home_win_pct=round(home_win_pct, 3),
            home_advantage_factor=round(home_advantage_factor, 3),
        )

        if existing is None:
            session.add(RefereeProfile(name=name, **values))
        else:
            for k, v in values.items():
                setattr(existing, k, v)

        upserted += 1

    await session.commit()
    console.print(
        f"[green]Upserted {upserted} referee profiles. "
        f"League home win pct: {league_home_win_pct:.1%}[/green]"
    )


async def cache_referee_fixtures(
    client: ApiFootballClient, session: AsyncSession
) -> None:
    result = await session.execute(
        select(Match.referee_name)
        .where(Match.referee_name.is_not(None))
        .distinct()
    )
    referees = [r[0] for r in result.all()]

    console.print(f"Pre-caching fixture data for {len(referees)} referees...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Referee fixtures"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("referees", total=len(referees))
        for name in referees:
            try:
                await client.get_referee_fixtures(
                    name, settings.superliga_league_id, settings.superliga_season
                )
            except Exception as exc:
                console.print(f"[yellow]{name} cache failed: {exc}[/yellow]")
            progress.advance(task)

    console.print("[green]Referee fixture cache populated.[/green]")


async def main() -> None:
    if not settings.api_football_key:
        console.print("[red]API_FOOTBALL_KEY not set — aborting.[/red]")
        return

    await init_db()
    client = ApiFootballClient()

    async with AsyncSessionLocal() as session:
        console.print("Building referee profiles from match data...")
        await build_referee_profiles(session)

        await cache_referee_fixtures(client, session)

    console.print("[bold green]Done.[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
