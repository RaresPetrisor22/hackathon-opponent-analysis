"""clean_stats.py — Post-process Match.stats_home / stats_away JSON columns.

Usage:
    cd backend
    uv run python scripts/clean_stats.py

What it does:
1. Drops `goals_prevented` from every stats dict (API never reports it for SuperLiga).
2. Computes the league-wide mean of `expected_goals` across all non-null
   team-match observations and fills nulls with that value.

Idempotent: safe to re-run after any ingest. No API calls.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal, init_db
from app.models.match import Match

console = Console()

DROP_KEYS = ("goals_prevented",)
IMPUTE_KEY = "expected_goals"


def drop_keys(d: dict | None) -> dict | None:
    if d is None:
        return None
    return {k: v for k, v in d.items() if k not in DROP_KEYS}


async def clean(session: AsyncSession) -> None:
    result = await session.execute(select(Match).where(Match.complete()))
    matches = result.scalars().all()

    # Pass 1: compute league mean for IMPUTE_KEY
    values: list[float] = []
    for m in matches:
        for blob in (m.stats_home, m.stats_away):
            if blob and blob.get(IMPUTE_KEY) is not None:
                values.append(float(blob[IMPUTE_KEY]))

    if not values:
        console.print(f"[red]No non-null {IMPUTE_KEY} values found — aborting.[/red]")
        return

    mean_val = round(sum(values) / len(values), 3)
    console.print(
        f"League mean {IMPUTE_KEY} = {mean_val} (over {len(values)} team-match observations)"
    )

    # Pass 2: drop unwanted keys + impute nulls
    dropped = 0
    imputed = 0
    for m in matches:
        for side in ("stats_home", "stats_away"):
            blob = getattr(m, side)
            if blob is None:
                continue

            new_blob = drop_keys(blob)
            had_drops = len(new_blob) != len(blob)

            if new_blob.get(IMPUTE_KEY) is None:
                new_blob[IMPUTE_KEY] = mean_val
                imputed += 1

            if had_drops:
                dropped += 1

            # Reassign so SQLAlchemy detects the change on JSON column
            setattr(m, side, new_blob)

    await session.commit()
    console.print(
        f"[green]Cleaned {len(matches)} matches: "
        f"dropped {DROP_KEYS} from {dropped} sides, "
        f"imputed {IMPUTE_KEY} on {imputed} sides.[/green]"
    )


async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        await clean(session)


if __name__ == "__main__":
    asyncio.run(main())
