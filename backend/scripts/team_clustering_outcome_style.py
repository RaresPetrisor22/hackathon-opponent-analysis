"""team_clustering_outcome_style.py — Visualisation for the chosen production
feature set: outcome+style (5 features) with StandardScaler + PCA reduction.

Features (per team, mean across all season matches):
  - possession_pct   : ball possession %
  - pass_accuracy    : pass completion %
  - long_shot_ratio  : shots_outsidebox / total_shots  (style: long-range tendency)
  - shot_quality     : shots_on_goal / total_shots     (style: shot selection)
  - goal_diff        : goals_for - goals_against       (per-match outcome signal)

Pipeline: StandardScaler -> PCA(90% var) -> KMeans(k).
Silhouette at k=4 ≈ 0.4459, at k=5 ≈ ? (printed at runtime).

Output:
  backend/data/team_clustering_outcome_style.png — 4-panel grid
  (rows = k values, cols = PCA, UMAP)

Usage:
  cd backend
  uv run python scripts/team_clustering_outcome_style.py
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
OUT_PATH = OUT_DIR / "team_clustering_outcome_style.png"

K_VALUES = (4, 5)
FEATURE_COLS = [
    "possession_pct",
    "pass_accuracy",
    "long_shot_ratio",
    "shot_quality",
    "goal_diff",
]

# Dark-theme palette aligned with the dossier UI accent
PALETTE = ["#00ff88", "#ff5d73", "#5da5ff", "#ffb84d", "#c084fc", "#22d3ee"]


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


async def load_team_matrix() -> tuple[pd.DataFrame, dict[int, str]]:
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
    return team_df[["team_id", "team_name", *FEATURE_COLS]], teams


# ---------------------------------------------------------------------------
# Pipeline: scale -> PCA(90%) -> KMeans
# ---------------------------------------------------------------------------

def fit_pipeline(X_raw: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray, float, PCA]:
    """Standardise, reduce to top-PCs (90% var), cluster with KMeans(k).

    Returns:
        labels: cluster assignment per row
        X_pca: PCA-reduced coords (used for clustering)
        silhouette: in PCA space (matches the sweep's measurement)
        pca_full: PCA fitted on standardised X (so callers can read loadings)
    """
    X_std = StandardScaler().fit_transform(X_raw)

    pca_full = PCA(random_state=42).fit(X_std)
    cum = np.cumsum(pca_full.explained_variance_ratio_)
    n_components = int(np.searchsorted(cum, 0.90)) + 1
    n_components = max(2, min(n_components, X_std.shape[1]))

    pca_reduced = PCA(n_components=n_components, random_state=42)
    X_pca = pca_reduced.fit_transform(X_std)

    km = KMeans(n_clusters=k, random_state=42, n_init=20)
    labels = km.fit_predict(X_pca)
    sil = silhouette_score(X_pca, labels)
    return labels, X_pca, sil, pca_full


# ---------------------------------------------------------------------------
# 2D projections for plotting (always 2D regardless of clustering space)
# ---------------------------------------------------------------------------

def project_pca_2d(X_raw: np.ndarray) -> tuple[np.ndarray, PCA]:
    X_std = StandardScaler().fit_transform(X_raw)
    pca = PCA(n_components=2, random_state=42)
    return pca.fit_transform(X_std), pca


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
# Plotting
# ---------------------------------------------------------------------------

def scatter(
    ax: plt.Axes,
    coords: np.ndarray,
    labels: np.ndarray,
    team_names: list[str],
    title: str,
    silhouette: float,
) -> None:
    ax.set_facecolor("#0a0e1a")
    for cluster_id in np.unique(labels):
        mask = labels == cluster_id
        ax.scatter(
            coords[mask, 0],
            coords[mask, 1],
            s=200,
            c=PALETTE[cluster_id % len(PALETTE)],
            edgecolors="white",
            linewidths=0.7,
            alpha=0.95,
            label=f"C{cluster_id}",
            zorder=3,
        )

    for i, name in enumerate(team_names):
        ax.annotate(
            name,
            (coords[i, 0], coords[i, 1]),
            xytext=(7, 6),
            textcoords="offset points",
            fontsize=8,
            color="white",
            zorder=4,
        )

    ax.set_title(f"{title}    silhouette = {silhouette:.3f}", fontsize=11, color="white")
    ax.tick_params(colors="#888", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#444")
    ax.grid(True, alpha=0.15, color="#666", linestyle="--", linewidth=0.5)
    ax.legend(
        loc="best",
        fontsize=8,
        facecolor="#0a0e1a",
        edgecolor="#444",
        labelcolor="white",
    )


def render_grid(team_df: pd.DataFrame) -> dict[int, dict[str, Any]]:
    X_raw = team_df[FEATURE_COLS].values
    team_names = team_df["team_name"].tolist()

    # 2D projections (computed once, shared across both rows)
    pca_coords, pca_2d_model = project_pca_2d(X_raw)
    umap_coords = project_umap_2d(X_raw)

    fig, axes = plt.subplots(
        len(K_VALUES), 2, figsize=(15, 6 * len(K_VALUES)), facecolor="#0a0e1a"
    )

    results: dict[int, dict[str, Any]] = {}
    for row_idx, k in enumerate(K_VALUES):
        labels, _, sil, pca_full = fit_pipeline(X_raw, k)
        results[k] = {"labels": labels, "silhouette": sil, "pca_full": pca_full}

        scatter(axes[row_idx, 0], pca_coords, labels, team_names, f"PCA — k={k}", sil)
        scatter(axes[row_idx, 1], umap_coords, labels, team_names, f"UMAP — k={k}", sil)

    fig.suptitle(
        "Team-Level Archetypes — outcome+style features (5 feat, std + PCA)",
        fontsize=14,
        color="white",
        y=0.995,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=150, facecolor="#0a0e1a")
    plt.close(fig)

    return {"results": results, "pca_2d": pca_2d_model}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_pca_loadings(pca_2d: PCA) -> None:
    print("\nPCA loadings (visualisation axes — 2D projection of standardised features):")
    print(f"  Explained variance: PC1 = {pca_2d.explained_variance_ratio_[0]:.1%}, "
          f"PC2 = {pca_2d.explained_variance_ratio_[1]:.1%}, "
          f"total = {sum(pca_2d.explained_variance_ratio_):.1%}")
    print(f"  {'feature':<20} {'PC1':>10} {'PC2':>10}")
    print("  " + "-" * 42)
    for i, col in enumerate(FEATURE_COLS):
        print(f"  {col:<20} {pca_2d.components_[0][i]:>10.3f} {pca_2d.components_[1][i]:>10.3f}")


def print_assignments(team_df: pd.DataFrame, results: dict[int, dict[str, Any]]) -> None:
    for k, info in results.items():
        labels = info["labels"]
        print(f"\nTeam assignments at k={k} (silhouette={info['silhouette']:.4f}):")
        for cluster_id in sorted(np.unique(labels)):
            members = team_df.loc[labels == cluster_id, "team_name"].tolist()
            print(f"  C{cluster_id} ({len(members)}): {', '.join(members)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    team_df, _ = await load_team_matrix()
    print(f"Loaded {len(team_df)} teams with {len(FEATURE_COLS)} features:")
    print(f"  {FEATURE_COLS}\n")

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print("Team-level matrix (mean across each team's matches):")
    print(team_df.round(3).to_string(index=False))

    output = render_grid(team_df)
    print_pca_loadings(output["pca_2d"])
    print_assignments(team_df, output["results"])

    print("\n" + "=" * 72)
    print(f"Saved visualisation: {OUT_PATH}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
