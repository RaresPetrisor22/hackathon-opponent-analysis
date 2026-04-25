"""team_silhouette_sweep.py — Push the team-level silhouette toward 0.4 at k=4.

Diagnosis from team_clustering_visualisation.py:
  - 'directness' = total_shots / total_passes spans only 0.02..0.04 → little signal.
  - 'pressing_proxy' = fouls is partly referee-driven noise.
  - We're not yet using outcome features (GF, GA, xG) that carry stylistic
    signal at the team level (a high-possession, low-GF team is structurally
    different from a high-possession, high-GF team).

This script sweeps the cross-product of:
  1. Feature sets       — 6 variants
  2. Scalers            — StandardScaler vs RobustScaler
  3. Cluster space      — raw features vs PCA-reduced (top components, 90% var)

Reports silhouette at k=4 for every combination and picks the winner.

Run:
    cd backend
    uv run python scripts/team_silhouette_sweep.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import RobustScaler, StandardScaler
from sqlalchemy import select

from app.db import AsyncSessionLocal, init_db
from app.models.match import Match
from app.models.team import Team

K = 4  # all comparisons fixed at k=4 per requirement


# ---------------------------------------------------------------------------
# Tolerant numeric reader
# ---------------------------------------------------------------------------

def _stat(d: dict[str, Any], k: str, default: float = 0.0) -> float:
    v = d.get(k) if d else None
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Per-match feature builders — each returns one team's per-match features.
# ---------------------------------------------------------------------------

def f_baseline(team: dict, opp: dict, gf: int, ga: int) -> dict[str, float]:
    """Current production set."""
    ts, os_ = _stat(team, "total_shots"), _stat(opp, "total_shots")
    tp = _stat(team, "total_passes")
    return {
        "possession_pct": _stat(team, "ball_possession"),
        "shots_ratio": ts / (ts + os_) if (ts + os_) else 0.5,
        "pass_accuracy": _stat(team, "passes_pct"),
        "pressing_proxy": _stat(team, "fouls"),
        "directness": ts / tp if tp else 0.0,
    }


def f_no_directness(team: dict, opp: dict, gf: int, ga: int) -> dict[str, float]:
    """Drop the noisy directness ratio entirely."""
    f = f_baseline(team, opp, gf, ga)
    f.pop("directness")
    return f


def f_long_shot_directness(team: dict, opp: dict, gf: int, ga: int) -> dict[str, float]:
    """Replace directness with shots_outsidebox / total_shots — a real style stat."""
    f = f_baseline(team, opp, gf, ga)
    ts = _stat(team, "total_shots")
    f["directness"] = _stat(team, "shots_outsidebox") / ts if ts else 0.0
    return f


def f_outcome_4(team: dict, opp: dict, gf: int, ga: int) -> dict[str, float]:
    """4 stylistic stats + goal_diff per match (per-match outcome signal)."""
    return {
        "possession_pct": _stat(team, "ball_possession"),
        "pass_accuracy": _stat(team, "passes_pct"),
        "long_shot_ratio": (
            _stat(team, "shots_outsidebox") / _stat(team, "total_shots")
            if _stat(team, "total_shots") else 0.0
        ),
        "shot_quality": (
            _stat(team, "shots_on_goal") / _stat(team, "total_shots")
            if _stat(team, "total_shots") else 0.0
        ),
        "goal_diff": float(gf - ga),
    }


def f_style_outcome(team: dict, opp: dict, gf: int, ga: int) -> dict[str, float]:
    """Style + outcome 6-feature set: drop pressing_proxy (refereeing noise),
    drop ratio-based directness, add outcome features."""
    ts = _stat(team, "total_shots")
    return {
        "possession_pct": _stat(team, "ball_possession"),
        "shots_ratio": (
            ts / (ts + _stat(opp, "total_shots"))
            if (ts + _stat(opp, "total_shots")) else 0.5
        ),
        "pass_accuracy": _stat(team, "passes_pct"),
        "long_shot_ratio": _stat(team, "shots_outsidebox") / ts if ts else 0.0,
        "goals_for": float(gf),
        "goals_against": float(ga),
    }


def f_minimal_3(team: dict, opp: dict, gf: int, ga: int) -> dict[str, float]:
    """The three highest-variance features at the team level: possession,
    pass accuracy, and goal differential. Hypothesis: fewer well-chosen
    features beat many noisy ones at this small N."""
    return {
        "possession_pct": _stat(team, "ball_possession"),
        "pass_accuracy": _stat(team, "passes_pct"),
        "goal_diff": float(gf - ga),
    }


FEATURE_SETS: list[tuple[str, Callable[..., dict[str, float]]]] = [
    ("baseline (5 feat)",            f_baseline),
    ("no directness (4 feat)",       f_no_directness),
    ("long-shot directness (5 feat)", f_long_shot_directness),
    ("outcome+style (5 feat)",       f_outcome_4),
    ("style+outcome (6 feat)",       f_style_outcome),
    ("minimal 3 feat",               f_minimal_3),
]


# ---------------------------------------------------------------------------
# Loader — fetch matches once, reuse across experiments.
# ---------------------------------------------------------------------------

async def fetch_matches() -> list[Match]:
    async with AsyncSessionLocal() as session:
        stmt = select(Match).where(Match.complete()).order_by(Match.date.asc())
        return list((await session.execute(stmt)).scalars().all())


async def fetch_team_names() -> dict[int, str]:
    async with AsyncSessionLocal() as session:
        return {
            t.id: t.name
            for t in (await session.execute(select(Team))).scalars().all()
        }


def build_team_matrix(
    matches: list[Match],
    builder: Callable[..., dict[str, float]],
) -> pd.DataFrame:
    """Build per-team mean feature matrix using the given per-match builder."""
    rows: list[dict[str, Any]] = []
    for m in matches:
        hs, as_ = m.stats_home or {}, m.stats_away or {}
        gh, ga = m.home_score or 0, m.away_score or 0
        rows.append({"team_id": m.home_team_id, **builder(hs, as_, gh, ga)})
        rows.append({"team_id": m.away_team_id, **builder(as_, hs, ga, gh)})

    match_df = pd.DataFrame(rows)
    feat_cols = [c for c in match_df.columns if c != "team_id"]
    team_df = match_df.groupby("team_id")[feat_cols].mean().reset_index()
    return team_df


# ---------------------------------------------------------------------------
# Scoring — sweep scaler × space (raw vs PCA) at fixed k=4.
# ---------------------------------------------------------------------------

SCALERS = [
    ("standard", StandardScaler()),
    ("robust", RobustScaler()),
]


def score_combo(
    team_df: pd.DataFrame,
    feat_cols: list[str],
    scaler_name: str,
    scaler,
    space: str,
) -> tuple[float, np.ndarray]:
    """Return (silhouette_at_k4, cluster_labels). space ∈ {"raw","pca"}."""
    X = scaler.fit_transform(team_df[feat_cols].values)

    if space == "pca":
        # Pick smallest n_components that explains >= 90% variance, max=4
        full = PCA(random_state=42).fit(X)
        cum = np.cumsum(full.explained_variance_ratio_)
        n_components = int(np.searchsorted(cum, 0.90)) + 1
        n_components = max(2, min(n_components, len(feat_cols), 4))
        X = PCA(n_components=n_components, random_state=42).fit_transform(X)

    km = KMeans(n_clusters=K, random_state=42, n_init=20)
    labels = km.fit_predict(X)
    return silhouette_score(X, labels), labels


async def main() -> None:
    await init_db()
    matches = await fetch_matches()
    teams = await fetch_team_names()
    print(f"Loaded {len(matches)} matches, {len(teams)} teams.\n")

    results: list[dict[str, Any]] = []

    for fs_name, builder in FEATURE_SETS:
        team_df = build_team_matrix(matches, builder)
        feat_cols = [c for c in team_df.columns if c != "team_id"]

        for sc_name, sc in SCALERS:
            for space in ("raw", "pca"):
                if space == "pca" and len(feat_cols) <= 2:
                    continue  # PCA on 2 features is meaningless
                # Fresh scaler each run — fit_transform mutates state
                sc_fresh = sc.__class__()
                sil, labels = score_combo(team_df, feat_cols, sc_name, sc_fresh, space)
                results.append({
                    "features": fs_name,
                    "n_feat": len(feat_cols),
                    "scaler": sc_name,
                    "space": space,
                    "silhouette": sil,
                    "labels": labels,
                    "team_df": team_df,
                    "feat_cols": feat_cols,
                })

    # ----- print full sweep -----
    print("=" * 88)
    print(f"FULL SWEEP — silhouette @ k={K}")
    print("=" * 88)
    print(f"{'features':<32} {'n':>3} {'scaler':>10} {'space':>6} {'silhouette':>12}")
    print("-" * 88)
    for r in results:
        print(
            f"{r['features']:<32} {r['n_feat']:>3} "
            f"{r['scaler']:>10} {r['space']:>6} {r['silhouette']:>12.4f}"
        )

    # ----- top 5 -----
    print("\n" + "=" * 88)
    print(f"TOP 5 (silhouette @ k={K}, target = 0.40)")
    print("=" * 88)
    top = sorted(results, key=lambda r: -r["silhouette"])[:5]
    for i, r in enumerate(top, 1):
        marker = "  ← target reached" if r["silhouette"] >= 0.40 else ""
        print(
            f"  {i}. {r['features']} | {r['scaler']} | {r['space']}"
            f" | sil={r['silhouette']:.4f}{marker}"
        )

    # ----- show team assignments for the winner -----
    winner = top[0]
    print("\n" + "=" * 88)
    print(f"WINNER — {winner['features']} | {winner['scaler']} | {winner['space']}")
    print(f"silhouette = {winner['silhouette']:.4f}")
    print("=" * 88)
    print(f"features used: {winner['feat_cols']}")
    labels = winner["labels"]
    team_df = winner["team_df"]
    team_df = team_df.assign(team_name=team_df["team_id"].map(teams))

    print()
    for ci in sorted(np.unique(labels)):
        members = team_df.loc[labels == ci, "team_name"].tolist()
        print(f"  C{ci}: {', '.join(members)}")


if __name__ == "__main__":
    asyncio.run(main())
