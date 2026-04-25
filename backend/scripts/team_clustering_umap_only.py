"""team_clustering_umap_only.py — Standalone UMAP visualisations of the
outcome+style 5-feature configuration at k=4 and k=5.

Pipeline (matches production candidate):
  StandardScaler -> PCA(90% var) -> KMeans(k)
  -> UMAP 2D for visualisation only (clusters are the real production labels)

Output:
  backend/data/team_clustering_umap_k4.png   — k=4 standalone
  backend/data/team_clustering_umap_k5.png   — k=5 standalone
  backend/data/team_clustering_umap_compare.png — side-by-side comparison

Usage:
  cd backend
  uv run python scripts/team_clustering_umap_only.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from app.db import AsyncSessionLocal, init_db
from app.models.match import Match
from app.models.team import Team

OUT_DIR = Path(__file__).parent.parent / "data"

K_VALUES = (4, 5)
FEATURE_COLS = [
    "possession_pct",
    "pass_accuracy",
    "long_shot_ratio",
    "shot_quality",
    "goal_diff",
]

# Dossier-aligned dark theme palette
PALETTE = ["#00ff88", "#ff5d73", "#5da5ff", "#ffb84d", "#c084fc", "#22d3ee"]
BG = "#0a0e1a"


# ---------------------------------------------------------------------------
# Feature extraction (matches f_outcome_4 from team_silhouette_sweep.py)
# ---------------------------------------------------------------------------

def _stat(d: dict[str, Any], k: str, default: float = 0.0) -> float:
    v = d.get(k) if d else None
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def per_match_features(
    team: dict[str, Any],
    opp: dict[str, Any],
    gf: int,
    ga: int,
) -> dict[str, float]:
    ts = _stat(team, "total_shots")
    return {
        "possession_pct": _stat(team, "ball_possession"),
        "pass_accuracy": _stat(team, "passes_pct"),
        "long_shot_ratio": _stat(team, "shots_outsidebox") / ts if ts else 0.0,
        "shot_quality": _stat(team, "shots_on_goal") / ts if ts else 0.0,
        "goal_diff": float(gf - ga),
    }


async def load_team_matrix() -> pd.DataFrame:
    await init_db()
    async with AsyncSessionLocal() as session:
        stmt = select(Match).where(Match.complete()).order_by(Match.date.asc())
        matches = list((await session.execute(stmt)).scalars().all())
        teams = {
            t.id: t.name
            for t in (await session.execute(select(Team))).scalars().all()
        }

    if not matches:
        raise SystemExit("No data — run ingest_season.py first.")

    rows: list[dict[str, Any]] = []
    for m in matches:
        hs, as_ = m.stats_home or {}, m.stats_away or {}
        gh, ga_ = m.home_score or 0, m.away_score or 0
        rows.append({"team_id": m.home_team_id, **per_match_features(hs, as_, gh, ga_)})
        rows.append({"team_id": m.away_team_id, **per_match_features(as_, hs, ga_, gh)})

    match_df = pd.DataFrame(rows)
    team_df = match_df.groupby("team_id")[FEATURE_COLS].mean().reset_index()
    team_df["team_name"] = team_df["team_id"].map(teams)
    return team_df[["team_id", "team_name", *FEATURE_COLS]]


# ---------------------------------------------------------------------------
# Production pipeline: scale -> PCA(90%) -> KMeans
# ---------------------------------------------------------------------------

def cluster_in_pca_space(X_raw: np.ndarray, k: int) -> tuple[np.ndarray, float]:
    X_std = StandardScaler().fit_transform(X_raw)
    pca = PCA(random_state=42).fit(X_std)
    cum = np.cumsum(pca.explained_variance_ratio_)
    n_components = int(np.searchsorted(cum, 0.90)) + 1
    n_components = max(2, min(n_components, X_std.shape[1]))

    X_pca = PCA(n_components=n_components, random_state=42).fit_transform(X_std)

    km = KMeans(n_clusters=k, random_state=42, n_init=20)
    labels = km.fit_predict(X_pca)
    return labels, silhouette_score(X_pca, labels)


def project_umap_2d(X_raw: np.ndarray) -> np.ndarray:
    X_std = StandardScaler().fit_transform(X_raw)
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


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def render_umap_panel(
    ax: plt.Axes,
    coords: np.ndarray,
    labels: np.ndarray,
    team_names: list[str],
    k: int,
    silhouette: float,
    *,
    show_hulls: bool = True,
) -> None:
    """Render a single UMAP scatter with team labels and optional cluster hulls."""
    ax.set_facecolor(BG)

    # Soft cluster hulls (centroid + dashed circle approximating cluster radius)
    if show_hulls:
        for cluster_id in np.unique(labels):
            mask = labels == cluster_id
            members = coords[mask]
            if len(members) < 2:
                continue
            centroid = members.mean(axis=0)
            radius = np.linalg.norm(members - centroid, axis=1).max() * 1.15
            hull = plt.Circle(
                centroid,
                radius,
                fill=True,
                alpha=0.08,
                color=PALETTE[cluster_id % len(PALETTE)],
                linewidth=0,
                zorder=1,
            )
            ax.add_patch(hull)

    # Cluster scatter
    for cluster_id in np.unique(labels):
        mask = labels == cluster_id
        ax.scatter(
            coords[mask, 0],
            coords[mask, 1],
            s=260,
            c=PALETTE[cluster_id % len(PALETTE)],
            edgecolors="white",
            linewidths=0.9,
            alpha=0.95,
            label=f"C{cluster_id} ({int(mask.sum())})",
            zorder=3,
        )

    # Team-name annotations
    for i, name in enumerate(team_names):
        ax.annotate(
            name,
            (coords[i, 0], coords[i, 1]),
            xytext=(8, 7),
            textcoords="offset points",
            fontsize=9,
            color="white",
            zorder=4,
        )

    ax.set_title(
        f"UMAP — k={k}    silhouette = {silhouette:.4f}",
        fontsize=13,
        color="white",
        pad=12,
    )
    ax.set_xlabel("UMAP-1", color="#bbb", fontsize=10)
    ax.set_ylabel("UMAP-2", color="#bbb", fontsize=10)
    ax.tick_params(colors="#888", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#444")
    ax.grid(True, alpha=0.15, color="#666", linestyle="--", linewidth=0.5)
    ax.legend(
        loc="best",
        fontsize=9,
        facecolor=BG,
        edgecolor="#444",
        labelcolor="white",
        title="Clusters",
        title_fontsize=9,
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def render_standalone(
    team_df: pd.DataFrame,
    coords: np.ndarray,
    labels: np.ndarray,
    silhouette: float,
    k: int,
) -> Path:
    fig, ax = plt.subplots(figsize=(11, 8), facecolor=BG)
    render_umap_panel(
        ax,
        coords,
        labels,
        team_df["team_name"].tolist(),
        k=k,
        silhouette=silhouette,
    )
    fig.suptitle(
        f"FC U Cluj — Tactical Archetypes (UMAP, k={k})",
        fontsize=15,
        color="white",
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out = OUT_DIR / f"team_clustering_umap_k{k}.png"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160, facecolor=BG)
    plt.close(fig)
    return out


def render_compare(
    team_df: pd.DataFrame,
    coords: np.ndarray,
    runs: dict[int, dict[str, Any]],
) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(20, 8.5), facecolor=BG)
    for ax, (k, info) in zip(axes, runs.items()):
        render_umap_panel(
            ax,
            coords,
            info["labels"],
            team_df["team_name"].tolist(),
            k=k,
            silhouette=info["silhouette"],
        )
    fig.suptitle(
        "Team-Level Tactical Archetypes — UMAP projection (outcome+style features)",
        fontsize=15,
        color="white",
        y=0.99,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out = OUT_DIR / "team_clustering_umap_compare.png"
    fig.savefig(out, dpi=160, facecolor=BG)
    plt.close(fig)
    return out


async def main() -> None:
    team_df = await load_team_matrix()
    print(f"Loaded {len(team_df)} teams, {len(FEATURE_COLS)} features.\n")

    X_raw = team_df[FEATURE_COLS].values

    # UMAP coords are projection-only — independent of k. Compute once.
    print("Computing UMAP 2D projection...")
    coords = project_umap_2d(X_raw)

    runs: dict[int, dict[str, Any]] = {}
    for k in K_VALUES:
        labels, sil = cluster_in_pca_space(X_raw, k)
        runs[k] = {"labels": labels, "silhouette": sil}
        print(f"  k={k}  silhouette={sil:.4f}")

    # Standalone PNGs
    print("\nWriting outputs:")
    for k, info in runs.items():
        out = render_standalone(team_df, coords, info["labels"], info["silhouette"], k)
        print(f"  {out}")

    # Side-by-side comparison
    cmp_path = render_compare(team_df, coords, runs)
    print(f"  {cmp_path}")

    # Print assignments for reference
    print("\nCluster assignments:")
    for k, info in runs.items():
        labels = info["labels"]
        print(f"\n  k={k} (silhouette={info['silhouette']:.4f}):")
        for ci in sorted(np.unique(labels)):
            members = team_df.loc[labels == ci, "team_name"].tolist()
            print(f"    C{ci} ({len(members)}): {', '.join(members)}")


if __name__ == "__main__":
    asyncio.run(main())
