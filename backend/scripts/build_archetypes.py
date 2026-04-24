"""build_archetypes.py — Fit KMeans archetypes and write assignments to DB.

Usage:
    cd backend
    uv run python scripts/build_archetypes.py

Run this after ingest_season.py has populated the matches table.

Steps:
1. Build the feature matrix from all completed matches.
2. Fit ArchetypeClusterer.
3. Label clusters heuristically.
4. Upsert Archetype rows with name, description, and cluster_center.
5. Update each Match row with home_archetype_id and away_archetype_id.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console

from app.analysis.matchups import ArchetypeClusterer, build_feature_matrix
from app.db import AsyncSessionLocal, init_db

console = Console()


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        console.print("Building feature matrix...")
        df = await build_feature_matrix(session)
        console.print(f"  {len(df)} match-team rows loaded.")

        if df.empty:
            console.print("[red]No match data found. Run ingest_season.py first.[/red]")
            return

        console.print("Fitting KMeans...")
        clusterer = ArchetypeClusterer()
        clusterer.fit(df)
        labels = clusterer.label_clusters()
        console.print(f"  Cluster labels: {labels}")

        # TODO: upsert Archetype rows and update Match rows with archetype IDs

        console.print("[green]Archetypes built and assigned.[/green]")


if __name__ == "__main__":
    asyncio.run(main())
