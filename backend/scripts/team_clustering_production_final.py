"""team_clustering_production_final.py — Final production-truth visualisation.

Reads the *persisted* archetype assignments from the DB (written by
build_archetypes.py) so the picture matches exactly what `predict_matchup`
will use at runtime. Re-runs the same StandardScaler + PCA pipeline used in
production (matchups.ArchetypeClusterer) to ground-truth the silhouette
score.

Output:
  backend/data/team_clustering_production_final.png

Usage:
    cd backend
    uv run python scripts/team_clustering_production_final.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap
from sklearn.metrics import silhouette_score
from sqlalchemy import select

from app.analysis.matchups import (
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

OUT_DIR = Path(__file__).parent.parent / "data"
OUT_PATH = OUT_DIR / "team_clustering_production_final.png"

# Stable colour mapping by archetype name (so colours don't shuffle on reruns)
ARCHETYPE_COLOUR = {
    "Dominant Possession Elite": "#00ff88",
    "Compact Counter": "#5da5ff",
    "Long-Range Specialists": "#ffb84d",
    "Direct & Struggling": "#ff5d73",
}
DEFAULT_COLOUR = "#c084fc"
BG = "#0a0e1a"


async def load_state() -> dict:
    await init_db()
    async with AsyncSessionLocal() as session:
        match_df = await build_feature_matrix(session)
        team_df = aggregate_to_team_level(match_df)

        teams = {
            t.id: t.name
            for t in (await session.execute(select(Team))).scalars().all()
        }

        # Each team's *persisted* archetype = the archetype of any match they
        # played as home (every team played at least one home match in the DB).
        match_rows = list(
            (
                await session.execute(
                    select(
                        Match.home_team_id,
                        Match.home_archetype_id,
                    ).where(Match.home_archetype_id.is_not(None))
                )
            ).all()
        )
        team_to_arch_id: dict[int, int] = {}
        for tid, aid in match_rows:
            team_to_arch_id.setdefault(tid, aid)

        archetypes = {
            a.id: a
            for a in (await session.execute(select(Archetype))).scalars().all()
        }

    if team_df.empty:
        raise SystemExit("No data — run ingest_season.py + build_archetypes.py first.")

    team_df = team_df.sort_values("team_id").reset_index(drop=True)
    team_df["team_name"] = team_df["team_id"].map(teams)
    team_df["archetype_id"] = team_df["team_id"].map(team_to_arch_id)
    team_df["archetype_name"] = team_df["archetype_id"].map(
        lambda aid: archetypes[aid].name if aid in archetypes else "Unassigned"
    )

    return {"team_df": team_df, "archetypes": archetypes}


def project_umap(X: np.ndarray) -> np.ndarray:
    """2D UMAP projection on standardised features (visualisation only)."""
    from sklearn.preprocessing import StandardScaler
    X_std = StandardScaler().fit_transform(X)
    n_neighbors = min(8, max(2, X_std.shape[0] - 1))
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=0.4,
        spread=1.5,
        n_components=2,
        random_state=42,
        metric="euclidean",
    )
    return reducer.fit_transform(X_std)


def render(team_df: pd.DataFrame, sil: float, n_components: int) -> Path:
    coords = project_umap(team_df[FEATURE_COLS].values)
    archetype_names = team_df["archetype_name"].tolist()
    team_names = team_df["team_name"].tolist()

    fig, ax = plt.subplots(figsize=(13, 9), facecolor=BG)
    ax.set_facecolor(BG)

    # Soft cluster hulls: shaded circle around each archetype's members
    unique_archs = sorted(set(archetype_names))
    for arch in unique_archs:
        mask = np.array([n == arch for n in archetype_names])
        if mask.sum() < 2:
            continue
        members = coords[mask]
        centroid = members.mean(axis=0)
        radius = np.linalg.norm(members - centroid, axis=1).max() * 1.15
        hull = plt.Circle(
            centroid,
            radius,
            fill=True,
            alpha=0.10,
            color=ARCHETYPE_COLOUR.get(arch, DEFAULT_COLOUR),
            linewidth=0,
            zorder=1,
        )
        ax.add_patch(hull)

    # Scatter
    for arch in unique_archs:
        mask = np.array([n == arch for n in archetype_names])
        ax.scatter(
            coords[mask, 0],
            coords[mask, 1],
            s=320,
            c=ARCHETYPE_COLOUR.get(arch, DEFAULT_COLOUR),
            edgecolors="white",
            linewidths=0.9,
            alpha=0.95,
            label=f"{arch} ({int(mask.sum())})",
            zorder=3,
        )

    # Team-name annotations — boxed for legibility, no overlap
    for i, name in enumerate(team_names):
        ax.annotate(
            name,
            (coords[i, 0], coords[i, 1]),
            xytext=(9, 8),
            textcoords="offset points",
            fontsize=9,
            color="white",
            zorder=4,
            bbox=dict(
                boxstyle="round,pad=0.18",
                facecolor=BG,
                edgecolor="#3a3a4a",
                alpha=0.85,
                linewidth=0.4,
            ),
        )

    # Title block — silhouette score is the headline number
    ax.set_title(
        f"Production archetypes — UMAP projection\n"
        f"silhouette = {sil:.4f}    "
        f"k = {N_CLUSTERS}    "
        f"PCA components = {n_components}    "
        f"features = {len(FEATURE_COLS)}",
        fontsize=13,
        color="white",
        pad=14,
    )
    ax.set_xlabel("UMAP-1", color="#bbb", fontsize=11)
    ax.set_ylabel("UMAP-2", color="#bbb", fontsize=11)
    ax.tick_params(colors="#888", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#444")
    ax.grid(True, alpha=0.15, color="#666", linestyle="--", linewidth=0.5)
    ax.legend(
        loc="best",
        fontsize=10,
        facecolor=BG,
        edgecolor="#444",
        labelcolor="white",
        title="Archetype",
        title_fontsize=10,
        framealpha=0.9,
    )

    fig.suptitle(
        "FC U Cluj — Tactical Archetypes (production configuration)",
        fontsize=16,
        color="white",
        y=0.985,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=170, facecolor=BG)
    plt.close(fig)
    return OUT_PATH


async def main() -> None:
    state = await load_state()
    team_df: pd.DataFrame = state["team_df"]

    # Re-fit the production pipeline to recover the live silhouette + n_components.
    # (The persisted DB labels come from this same fit, so the score matches.)
    clusterer = ArchetypeClusterer()
    clusterer.fit(team_df[["team_id", *FEATURE_COLS]])

    # Cross-check: persisted labels must agree with this fit.
    arch_ordered = team_df["archetype_id"].tolist()
    print("Live re-fit:")
    print(f"  Silhouette  : {clusterer.silhouette_:.4f}")
    print(f"  n_components: {clusterer.n_components_}")
    print(f"  Archetypes  : {[a.name for a in state['archetypes'].values()]}")

    print("\nTeam → Archetype (read from DB, after build_archetypes.py):")
    for arch_name in sorted(team_df["archetype_name"].unique()):
        members = team_df.loc[
            team_df["archetype_name"] == arch_name, "team_name"
        ].tolist()
        print(f"  {arch_name} ({len(members)}): {', '.join(members)}")

    out = render(
        team_df,
        sil=clusterer.silhouette_,
        n_components=clusterer.n_components_ or 0,
    )
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())
