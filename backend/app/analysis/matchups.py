from __future__ import annotations

"""Matchup Intelligence — the hero feature.

Approach
--------
1. For every match in the DB, extract a 6-dimensional feature vector that
   describes how each team played in that match:
     - possession_pct      : ball possession %
     - shots_ratio         : team_shots / (team_shots + opp_shots)
     - pass_accuracy       : pass completion %
     - pressing_proxy      : fouls committed (no tackle data in API-Football,
                             so this is a single-stat proxy)
     - directness          : total_shots / total_passes (shots-per-pass —
                             higher = more direct, lower = patient build-up).
                             API-Football has no long-pass count, so we use
                             this ratio as the closest available substitute.

   Note: an earlier draft included a 6th feature `season_form_rating`
   (rolling goal differential). Silhouette + inertia sweeps showed it was
   collinear with possession + shots_ratio + pass_accuracy and dropped the
   silhouette score at every k. It was removed.

2. Normalise all features with sklearn StandardScaler.

3. Fit KMeans with k=5 (tunable). Label clusters with human-readable names
   based on centroid values:
     - "High-Press Possession"
     - "Low-Block Counter"
     - "Direct Physical"
     - "Patient Build-Up"
     - "Balanced Mid-Block"

4. Assign each match to an archetype and persist via build_archetypes.py.

5. For a given opponent: aggregate W/D/L and avg goals-for/against per
   archetype using their match history.

6. For FC U Cluj: compute their own feature vector (mean across all their
   matches), find the nearest archetype centroid, and surface the prediction.

No coordinate data is used. All features come from aggregated per-match stats
stored in Match.stats_home / Match.stats_away (JSON).
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.schemas.dossier import ArchetypeRecord, MatchupSection

FEATURE_COLS = [
    "possession_pct",
    "shots_ratio",
    "pass_accuracy",
    "pressing_proxy",
    "directness",
]

N_CLUSTERS = 5

ARCHETYPE_LABELS = [
    "High-Press Possession",
    "Low-Block Counter",
    "Direct Physical",
    "Patient Build-Up",
    "Balanced Mid-Block",
]


class ArchetypeClusterer:
    """Fits and stores KMeans archetypes from match data."""

    def __init__(self) -> None:
        self.kmeans: KMeans | None = None
        self.scaler: StandardScaler = StandardScaler()
        self.cluster_centers_: np.ndarray | None = None

    def fit(self, feature_matrix: pd.DataFrame) -> None:
        """Fit scaler + KMeans on the provided feature matrix.

        Args:
            feature_matrix: DataFrame with columns == FEATURE_COLS, one row per match.
        """
        # TODO: implement
        X = self.scaler.fit_transform(feature_matrix[FEATURE_COLS].values)
        self.kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init="auto")
        self.kmeans.fit(X)
        self.cluster_centers_ = self.scaler.inverse_transform(self.kmeans.cluster_centers_)

    def predict(self, features: dict[str, float]) -> int:
        """Return cluster index for a single feature dict."""
        # TODO: implement
        if self.kmeans is None:
            raise RuntimeError("Clusterer not fitted yet.")
        vec = np.array([[features[c] for c in FEATURE_COLS]])
        scaled = self.scaler.transform(vec)
        return int(self.kmeans.predict(scaled)[0])

    def label_clusters(self) -> dict[int, str]:
        """Assign human labels to cluster indices based on centroid values."""
        # TODO: implement heuristic labelling from centroid dimensions
        return {i: ARCHETYPE_LABELS[i % len(ARCHETYPE_LABELS)] for i in range(N_CLUSTERS)}


def _stat(d: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Read a numeric stat, treating missing keys and None values as `default`."""
    v = d.get(key)
    if v is None:
        return default
    return float(v)


def classify_match(
    team_stats: dict[str, Any],
    opp_stats: dict[str, Any],
) -> dict[str, float]:
    """Extract a single team's per-match feature vector.

    Returns a dict whose keys exactly match FEATURE_COLS. All features come
    from the two stats dicts — no team-level aggregates needed.

    Args:
        team_stats: stats_home or stats_away for the team being classified.
        opp_stats:  the opposing team's stats from the same match.
    """
    team_shots = _stat(team_stats, "total_shots")
    opp_shots = _stat(opp_stats, "total_shots")
    total_shots = team_shots + opp_shots

    team_passes = _stat(team_stats, "total_passes")

    return {
        "possession_pct": _stat(team_stats, "ball_possession"),
        "shots_ratio": team_shots / total_shots if total_shots > 0 else 0.5,
        "pass_accuracy": _stat(team_stats, "passes_pct"),
        "pressing_proxy": _stat(team_stats, "fouls"),
        "directness": team_shots / team_passes if team_passes > 0 else 0.0,
    }


async def build_feature_matrix(session: AsyncSession) -> pd.DataFrame:
    """Query all completed matches from the DB and build the full feature matrix.

    Each completed match contributes TWO rows — one per team — so the resulting
    DataFrame has 2 × (#complete matches) rows. Columns are:
        match_id, team_id, season, *FEATURE_COLS

    Only matches passing Match.complete() are included — five 2024-25 fixtures
    have no stats from the API and must not distort cluster centroids.
    """
    from sqlalchemy import select

    stmt = select(Match).where(Match.complete())
    matches = list((await session.execute(stmt)).scalars().all())

    columns = ["match_id", "team_id", "season", *FEATURE_COLS]
    if not matches:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for match in matches:
        home_stats = match.stats_home or {}
        away_stats = match.stats_away or {}

        rows.append({
            "match_id": match.id,
            "team_id": match.home_team_id,
            "season": match.season_id,
            **classify_match(home_stats, away_stats),
        })
        rows.append({
            "match_id": match.id,
            "team_id": match.away_team_id,
            "season": match.season_id,
            **classify_match(away_stats, home_stats),
        })

    return pd.DataFrame(rows, columns=columns)


async def get_team_record_vs_archetypes(
    team_id: int,
    session: AsyncSession,
) -> list[ArchetypeRecord]:
    """Compute the team's W/D/L record and goal averages broken down by archetype.

    Looks at matches where the opposing team was assigned a given archetype,
    which tells us: "how does this team perform when facing each style?"
    """
    # TODO: implement
    return []


async def predict_matchup(
    opponent_id: int,
    fcu_team_id: int,
    session: AsyncSession,
) -> MatchupSection:
    """Main entry point. Returns the full MatchupSection for the dossier.

    Steps:
    1. Load archetype assignments from DB (built by build_archetypes.py).
    2. Get opponent's record vs each archetype.
    3. Compute FCU's own feature vector, find nearest archetype.
    4. Synthesise prediction summary.
    """
    # TODO: implement
    raise NotImplementedError
