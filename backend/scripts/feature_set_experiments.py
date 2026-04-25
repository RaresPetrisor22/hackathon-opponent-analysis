"""feature_set_experiments.py — Try alternative feature definitions and
re-score with silhouette + inertia for k in 2..8.

This script does NOT modify matchups.py — it builds its own feature matrix
locally so we can compare apples-to-apples without touching shared code.

Each experiment defines:
  - a name
  - the list of feature columns
  - a function (team_stats, opp_stats) -> dict[col, float]

Run:
    cd backend
    uv run python scripts/feature_set_experiments.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from app.db import AsyncSessionLocal, init_db
from app.models.match import Match


# ---------------------------------------------------------------------------
# Helper: tolerant numeric reader
# ---------------------------------------------------------------------------
def _stat(d: dict[str, Any], k: str, default: float = 0.0) -> float:
    v = d.get(k) if d else None
    return float(v) if v is not None else default


# ---------------------------------------------------------------------------
# Feature builders — each takes (team_stats, opp_stats) -> dict
# ---------------------------------------------------------------------------

def baseline_features(team: dict, opp: dict) -> dict[str, float]:
    """Current production feature set (matchups.py)."""
    ts, os_ = _stat(team, "total_shots"), _stat(opp, "total_shots")
    tp = _stat(team, "total_passes")
    return {
        "possession_pct": _stat(team, "ball_possession"),
        "shots_ratio": ts / (ts + os_) if (ts + os_) else 0.5,
        "pass_accuracy": _stat(team, "passes_pct"),
        "pressing_proxy": _stat(team, "fouls"),
        "directness": ts / tp if tp else 0.0,
        # season_form_rating handled at matrix-build level
    }


def no_form(team: dict, opp: dict) -> dict[str, float]:
    """Drop season_form_rating (it's collinear with possession + pass_acc)."""
    return baseline_features(team, opp)


def long_shot_directness(team: dict, opp: dict) -> dict[str, float]:
    """Replace shots/passes 'directness' with shots_outsidebox / total_shots —
    a true style stat (long-range vs box-entry tendency)."""
    f = baseline_features(team, opp)
    ts = _stat(team, "total_shots")
    f["directness"] = _stat(team, "shots_outsidebox") / ts if ts else 0.0
    return f


def with_xg(team: dict, opp: dict) -> dict[str, float]:
    """Add expected_goals as a 6th orthogonal feature (attacking intent)."""
    f = baseline_features(team, opp)
    f["xg"] = _stat(team, "expected_goals")
    return f


def long_shot_plus_xg(team: dict, opp: dict) -> dict[str, float]:
    """Long-shot directness + xG (the two style/intent features) on top
    of the 4 baseline structural stats."""
    f = long_shot_directness(team, opp)
    f["xg"] = _stat(team, "expected_goals")
    return f


def style_only(team: dict, opp: dict) -> dict[str, float]:
    """Remove possession/shots_ratio (the dominance axis) — keep only
    style differentiators. Hypothesis: this surfaces tactical archetypes
    instead of a quality continuum."""
    ts = _stat(team, "total_shots")
    tp = _stat(team, "total_passes")
    return {
        "pass_accuracy": _stat(team, "passes_pct"),
        "pressing_proxy": _stat(team, "fouls"),
        "long_shot_ratio": _stat(team, "shots_outsidebox") / ts if ts else 0.0,
        "shots_per_pass": ts / tp if tp else 0.0,
        "corner_share": _stat(team, "corner_kicks"),
    }


EXPERIMENTS: list[tuple[str, Callable[[dict, dict], dict[str, float]], bool]] = [
    # (name, builder, include_form_rating?)
    ("baseline (current)",         baseline_features,      True),
    ("baseline minus form",        no_form,                False),
    ("long-shot directness",       long_shot_directness,   True),
    ("baseline + xG",              with_xg,                True),
    ("long-shot + xG",             long_shot_plus_xg,      True),
    ("style-only (no dominance)",  style_only,             False),
]


# ---------------------------------------------------------------------------
# Matrix builder
# ---------------------------------------------------------------------------
FORM_WINDOW = 5


def _rolling(history: list[int]) -> float:
    if not history:
        return 0.0
    recent = history[-FORM_WINDOW:]
    return sum(recent) / len(recent)


async def fetch_matches() -> list[Match]:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Match)
            .where(Match.complete(), Match.date.is_not(None))
            .order_by(Match.date.asc())
        )
        return list((await session.execute(stmt)).scalars().all())


def build_matrix(
    matches: list[Match],
    builder: Callable[[dict, dict], dict[str, float]],
    include_form: bool,
) -> pd.DataFrame:
    history: dict[int, list[int]] = {}
    rows: list[dict[str, Any]] = []
    for m in matches:
        hs, as_ = m.stats_home or {}, m.stats_away or {}
        h_form, a_form = _rolling(history.get(m.home_team_id, [])), _rolling(history.get(m.away_team_id, []))

        h_feat = builder(hs, as_)
        a_feat = builder(as_, hs)
        if include_form:
            h_feat["season_form_rating"] = h_form
            a_feat["season_form_rating"] = a_form

        rows.append({"match_id": m.id, "team_id": m.home_team_id, **h_feat})
        rows.append({"match_id": m.id, "team_id": m.away_team_id, **a_feat})

        if m.home_score is not None and m.away_score is not None:
            diff = m.home_score - m.away_score
            history.setdefault(m.home_team_id, []).append(diff)
            history.setdefault(m.away_team_id, []).append(-diff)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------
K_RANGE = range(2, 9)


def score_features(df: pd.DataFrame, feat_cols: list[str]) -> dict[int, tuple[float, float]]:
    X = StandardScaler().fit_transform(df[feat_cols].values)
    out: dict[int, tuple[float, float]] = {}
    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        out[k] = (silhouette_score(X, labels), float(km.inertia_))
    return out


async def main() -> None:
    await init_db()
    matches = await fetch_matches()
    print(f"Loaded {len(matches)} matches with stats.\n")

    summary: list[tuple[str, list[str], int, float]] = []
    for name, builder, include_form in EXPERIMENTS:
        df = build_matrix(matches, builder, include_form)
        feat_cols = [c for c in df.columns if c not in ("match_id", "team_id")]
        scores = score_features(df, feat_cols)

        print(f"=== {name} ({len(feat_cols)} features: {feat_cols}) ===")
        print("  k | silhouette |  inertia")
        for k, (sil, iner) in scores.items():
            print(f"  {k} | {sil:10.4f} | {iner:8.1f}")
        best_k = max(scores, key=lambda k: scores[k][0])
        best_sil = scores[best_k][0]
        # also k=5 score for product-friendly comparison
        sil_at_5 = scores.get(5, (None,))[0]
        print(f"  -> best k={best_k} (sil={best_sil:.4f}); at k=5 sil={sil_at_5:.4f}\n")
        summary.append((name, feat_cols, best_k, best_sil))

    # Final summary
    print("=" * 80)
    print("SUMMARY (sorted by best silhouette)")
    print("=" * 80)
    summary.sort(key=lambda r: -r[3])
    print(f"{'experiment':<32} | {'#feat':>5} | {'best k':>6} | {'silhouette':>10}")
    print("-" * 70)
    for name, cols, k, sil in summary:
        print(f"{name:<32} | {len(cols):>5} | {k:>6} | {sil:>10.4f}")


if __name__ == "__main__":
    asyncio.run(main())
