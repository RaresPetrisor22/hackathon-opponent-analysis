"""team_clustering_visualisation.py — PCA + UMAP visualisation of team-level archetypes.

Follow-up to team_level_experiment.py. The team-level approach (averaging each
team's matches into a single row) raised the silhouette score, but with only 16
data points the clusters are hard to validate from numbers alone. This script
projects them into 2D so you can eyeball cluster compactness and separation.

Two projections side-by-side:
  - PCA   : linear, preserves global variance structure. Axes are
            interpretable (loadings printed below the plot).
  - UMAP  : non-linear, preserves local neighbourhood structure. Better at
            revealing clusters but axes are not interpretable.

For each projection we colour points by their KMeans cluster, label them with
team names, and overlay cluster centroids. We run for k=4, 5, 6 and write all
three side-by-sides to a single PNG.

Output:
    backend/data/team_clustering_pca_umap.png

Usage:
    cd backend
    uv run python scripts/team_clustering_visualisation.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# UTF-8 stdout for Romanian team names on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")  # no display backend — write PNGs only
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from app.analysis.matchups import FEATURE_COLS, build_feature_matrix
from app.db import AsyncSessionLocal, init_db
from app.models.team import Team

OUT_DIR = Path(__file__).parent.parent / "data"
OUT_PATH = OUT_DIR / "team_clustering_pca_umap.png"

# k values to project; first one is the "headline" used for cluster colours
K_VALUES = (4, 5, 6)

# Discrete colour cycle that works well on a dark-ish UI background
PALETTE = ["#00ff88", "#ff5d73", "#5da5ff", "#ffb84d", "#c084fc", "#22d3ee"]


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

async def load_team_matrix() -> tuple[pd.DataFrame, dict[int, str]]:
    """Build the team-level matrix from match-level features.

    Returns:
        team_df: one row per team, columns = ["team_id", "team_name", *FEATURE_COLS]
        teams:   {team_id: team_name}
    """
    await init_db()
    async with AsyncSessionLocal() as session:
        match_df = await build_feature_matrix(session)
        teams = {
            t.id: t.name
            for t in (await session.execute(select(Team))).scalars().all()
        }

    if match_df.empty:
        raise SystemExit("No match data — run ingest_season.py first.")

    team_df = (
        match_df.groupby("team_id")[FEATURE_COLS]
        .mean()
        .reset_index()
    )
    team_df["team_name"] = team_df["team_id"].map(teams)
    team_df = team_df[["team_id", "team_name", *FEATURE_COLS]]
    return team_df, teams


# ---------------------------------------------------------------------------
# Clustering + projection helpers
# ---------------------------------------------------------------------------

def fit_clusters(X: np.ndarray, k: int) -> tuple[np.ndarray, float, KMeans]:
    """Fit KMeans, return (labels, silhouette, model)."""
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    sil = silhouette_score(X, labels) if k > 1 else float("nan")
    return labels, sil, km


def pca_projection(X: np.ndarray) -> tuple[np.ndarray, PCA]:
    """2D PCA projection. Returns coords + fitted PCA (for loadings inspection)."""
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)
    return coords, pca


def umap_projection(X: np.ndarray) -> np.ndarray:
    """2D UMAP projection.

    With only 16 points we use small n_neighbors. Spread + min_dist tuned so
    clusters don't collapse on top of each other on the plot.
    """
    n_neighbors = min(8, max(2, X.shape[0] - 1))
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=0.4,
        spread=1.5,
        n_components=2,
        random_state=42,
        metric="euclidean",
    )
    return reducer.fit_transform(X)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def scatter_with_labels(
    ax: plt.Axes,
    coords: np.ndarray,
    labels: np.ndarray,
    team_names: list[str],
    title: str,
    silhouette: float,
) -> None:
    """Render one scatter panel with coloured clusters + team-name annotations."""
    ax.set_facecolor("#0a0e1a")
    for cluster_id in np.unique(labels):
        mask = labels == cluster_id
        ax.scatter(
            coords[mask, 0],
            coords[mask, 1],
            s=180,
            c=PALETTE[cluster_id % len(PALETTE)],
            edgecolors="white",
            linewidths=0.6,
            alpha=0.95,
            label=f"C{cluster_id}",
            zorder=3,
        )

    for i, name in enumerate(team_names):
        ax.annotate(
            name,
            (coords[i, 0], coords[i, 1]),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=7.5,
            color="white",
            zorder=4,
        )

    ax.set_title(f"{title}\nsilhouette = {silhouette:.3f}", fontsize=10, color="white")
    ax.tick_params(colors="#888", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#444")
    ax.grid(True, alpha=0.15, color="#666", linestyle="--", linewidth=0.5)
    ax.legend(
        loc="best",
        fontsize=7,
        facecolor="#0a0e1a",
        edgecolor="#444",
        labelcolor="white",
    )


def render_grid(team_df: pd.DataFrame, X: np.ndarray) -> dict[int, dict]:
    """Render a (rows = K_VALUES) x (cols = PCA, UMAP) grid of scatter plots.

    Returns a per-k results dict for textual reporting.
    """
    pca_coords, pca_model = pca_projection(X)
    umap_coords = umap_projection(X)
    team_names = team_df["team_name"].tolist()

    n_rows = len(K_VALUES)
    fig, axes = plt.subplots(
        n_rows, 2, figsize=(14, 5.2 * n_rows), facecolor="#0a0e1a"
    )
    if n_rows == 1:
        axes = np.array([axes])

    results: dict[int, dict] = {}

    for row_idx, k in enumerate(K_VALUES):
        labels, sil, km = fit_clusters(X, k)
        results[k] = {
            "labels": labels,
            "silhouette": sil,
            "kmeans": km,
            "centers_scaled": km.cluster_centers_,
        }
        scatter_with_labels(
            axes[row_idx, 0],
            pca_coords,
            labels,
            team_names,
            f"PCA — k={k}",
            sil,
        )
        scatter_with_labels(
            axes[row_idx, 1],
            umap_coords,
            labels,
            team_names,
            f"UMAP — k={k}",
            sil,
        )

    fig.suptitle(
        "Team-Level Tactical Archetypes — PCA vs UMAP projection",
        fontsize=14,
        color="white",
        y=0.995,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.99])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=150, facecolor="#0a0e1a")
    plt.close(fig)

    return {
        "results": results,
        "pca_model": pca_model,
        "pca_coords": pca_coords,
        "umap_coords": umap_coords,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_pca_loadings(pca: PCA, feat_cols: list[str]) -> None:
    """Show how much each original feature contributes to each PC axis."""
    print("\nPCA loadings (how each feature maps onto PC axes):")
    print(f"  Explained variance: PC1 = {pca.explained_variance_ratio_[0]:.1%}, "
          f"PC2 = {pca.explained_variance_ratio_[1]:.1%}, "
          f"total = {sum(pca.explained_variance_ratio_):.1%}")
    print(f"  {'feature':<20} {'PC1':>10} {'PC2':>10}")
    print("  " + "-" * 42)
    for i, col in enumerate(feat_cols):
        print(f"  {col:<20} {pca.components_[0][i]:>10.3f} {pca.components_[1][i]:>10.3f}")


def print_team_assignments(team_df: pd.DataFrame, results: dict) -> None:
    """For each k, print which teams went into which cluster."""
    for k, info in results.items():
        labels = info["labels"]
        print(f"\nTeam assignments at k={k} (silhouette={info['silhouette']:.3f}):")
        for cluster_id in sorted(np.unique(labels)):
            members = team_df.loc[labels == cluster_id, "team_name"].tolist()
            print(f"  C{cluster_id}: {', '.join(members)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    team_df, _ = await load_team_matrix()
    print(f"Loaded {len(team_df)} teams with {len(FEATURE_COLS)} features:")
    print(f"  features: {FEATURE_COLS}\n")

    # Print the team-level matrix (for sanity-check)
    print("Team-level feature matrix (mean across each team's matches):")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print(team_df.round(2).to_string(index=False))

    # Standardise once and reuse for KMeans, PCA, UMAP
    scaler = StandardScaler()
    X = scaler.fit_transform(team_df[FEATURE_COLS].values)

    # Build all plots and capture the per-k results
    output = render_grid(team_df, X)

    # Reporting
    print_pca_loadings(output["pca_model"], FEATURE_COLS)
    print_team_assignments(team_df, output["results"])

    print("\n" + "=" * 72)
    print(f"Saved visualisation: {OUT_PATH}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
