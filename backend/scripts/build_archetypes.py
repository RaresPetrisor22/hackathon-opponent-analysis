"""build_archetypes.py — Fit team-level archetypes and persist to the DB.

Pipeline (matches app/analysis/matchups.py production config):
  per-match features -> mean per team -> StandardScaler -> PCA(>= 90% var)
  -> KMeans(k=4)

Each TEAM is assigned exactly one archetype. Each match's home_archetype_id /
away_archetype_id is set to the corresponding team's archetype.

Usage:
    cd backend
    uv run python scripts/build_archetypes.py

Run this after ingest_season.py has populated the matches table.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table
from sqlalchemy import select

from app.analysis.matchups import (
    ARCHETYPE_DESCRIPTIONS,
    FEATURE_COLS,
    N_CLUSTERS,
    ArchetypeClusterer,
    aggregate_to_team_level,
    build_feature_matrix,
)
from app.db import AsyncSessionLocal, init_db
from app.models.archetype import Archetype
from app.models.match import Match
from app.models.team import Team

console = Console()


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        # ---- Step 1: build feature matrices ----
        console.print("[bold]Step 1[/bold] Building feature matrix...")
        match_df = await build_feature_matrix(session)
        console.print(f"  Match-level rows : [cyan]{len(match_df)}[/cyan]")

        if match_df.empty:
            console.print("[red]No match data — run ingest_season.py first.[/red]")
            return

        team_df = aggregate_to_team_level(match_df)
        console.print(f"  Team-level rows  : [cyan]{len(team_df)}[/cyan]")

        # ---- Step 2: fit pipeline ----
        console.print(f"\n[bold]Step 2[/bold] Fitting StandardScaler -> PCA -> KMeans(k={N_CLUSTERS})...")
        clusterer = ArchetypeClusterer()
        clusterer.fit(team_df)

        console.print(
            f"  PCA components retained : [cyan]{clusterer.n_components_}[/cyan] "
            f"(>= 90% variance)"
        )
        console.print(
            f"  Silhouette (team-level) : [bold green]{clusterer.silhouette_:.4f}[/bold green]"
        )

        labels: dict[int, str] = clusterer.label_clusters()

        # Display cluster signatures (centroids in original feature units)
        sig = Table(title="Cluster Signatures (membership-mean centroids)", show_lines=True)
        sig.add_column("Cluster", style="bold")
        sig.add_column("Label", style="cyan")
        for col in FEATURE_COLS:
            sig.add_column(col, justify="right")
        for ci in range(N_CLUSTERS):
            center = clusterer.cluster_centers_original_[ci]
            sig.add_row(
                str(ci), labels[ci], *[f"{v:.3f}" for v in center]
            )
        console.print(sig)

        # ---- Step 3: upsert Archetype rows ----
        console.print("\n[bold]Step 3[/bold] Upserting Archetype rows...")
        cluster_to_arch_id: dict[int, int] = {}

        for ci in range(N_CLUSTERS):
            label = labels[ci]
            description = ARCHETYPE_DESCRIPTIONS.get(label, "")
            center = clusterer.cluster_centers_original_[ci].tolist()

            existing = (
                await session.execute(select(Archetype).where(Archetype.name == label))
            ).scalar_one_or_none()

            if existing is None:
                arch = Archetype(
                    name=label,
                    description=description,
                    cluster_center=center,
                    assigned_match_ids=[],
                )
                session.add(arch)
            else:
                existing.cluster_center = center
                existing.description = description
                arch = existing

            await session.flush()
            cluster_to_arch_id[ci] = arch.id
            console.print(f"  cluster {ci} -> '{label}' (id={arch.id})")

        await session.commit()

        # ---- Step 4: stamp every team and every match ----
        console.print("\n[bold]Step 4[/bold] Mapping teams -> archetypes...")
        team_to_archetype: dict[int, int] = {}
        team_names_lookup = {
            t.id: t.name
            for t in (await session.execute(select(Team))).scalars().all()
        }

        cluster_assignments = Table(title="Team -> Archetype assignments", show_lines=False)
        cluster_assignments.add_column("Archetype", style="cyan")
        cluster_assignments.add_column("Teams")
        members_by_arch: dict[int, list[str]] = {ci: [] for ci in range(N_CLUSTERS)}

        for i, row in team_df.iterrows():
            tid = int(row["team_id"])
            cluster_idx = int(clusterer.team_labels_[i])
            arch_id = cluster_to_arch_id[cluster_idx]
            team_to_archetype[tid] = arch_id
            members_by_arch[cluster_idx].append(team_names_lookup.get(tid, f"team_{tid}"))

        for ci in range(N_CLUSTERS):
            cluster_assignments.add_row(
                labels[ci], ", ".join(sorted(members_by_arch[ci]))
            )
        console.print(cluster_assignments)

        # ---- Step 5: stamp matches ----
        console.print("\n[bold]Step 5[/bold] Stamping match.home_archetype_id / away_archetype_id...")
        all_matches = list(
            (await session.execute(select(Match).where(Match.complete()))).scalars().all()
        )

        archetype_to_match_ids: dict[int, set[int]] = {
            aid: set() for aid in cluster_to_arch_id.values()
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Stamping matches"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("matches", total=len(all_matches))
            for m in all_matches:
                home_arch = team_to_archetype.get(m.home_team_id)
                away_arch = team_to_archetype.get(m.away_team_id)
                m.home_archetype_id = home_arch
                m.away_archetype_id = away_arch
                if home_arch:
                    archetype_to_match_ids[home_arch].add(m.id)
                if away_arch:
                    archetype_to_match_ids[away_arch].add(m.id)
                progress.advance(task)

        # Update assigned_match_ids on each Archetype
        for arch_id, match_ids in archetype_to_match_ids.items():
            arch = await session.get(Archetype, arch_id)
            if arch:
                arch.assigned_match_ids = sorted(match_ids)

        await session.commit()

        # ---- Final summary ----
        console.print()
        console.print("[bold green]Archetypes built and assigned.[/bold green]")
        summary = Table(title="Archetype Assignment Summary", show_lines=True)
        summary.add_column("Archetype", style="cyan")
        summary.add_column("Teams", justify="right")
        summary.add_column("Matches", justify="right")
        for ci in range(N_CLUSTERS):
            arch_id = cluster_to_arch_id[ci]
            summary.add_row(
                labels[ci],
                str(len(members_by_arch[ci])),
                str(len(archetype_to_match_ids[arch_id])),
            )
        console.print(summary)


if __name__ == "__main__":
    asyncio.run(main())
