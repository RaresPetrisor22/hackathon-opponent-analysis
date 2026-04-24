from __future__ import annotations

"""Matchup Intelligence — the hero feature.

Approach
--------
1. For every match in the DB, extract a 6-dimensional feature vector that
   describes how the *opposing* team played (from the perspective of the team
   we're analysing):
     - possession_pct      : ball possession %
     - shots_ratio         : shots / (shots + opponent shots)
     - pass_accuracy       : pass completion %
     - pressing_proxy      : fouls committed + (tackles attempted — proxy only,
                             no coordinate data available)
     - directness          : long passes / total passes
     - season_form_rating  : rolling average of goals scored - conceded over
                             last N matches (quality proxy)

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

from app.schemas.dossier import ArchetypeRecord, MatchupSection

FEATURE_COLS = [
    "possession_pct",
    "shots_ratio",
    "pass_accuracy",
    "pressing_proxy",
    "directness",
    "season_form_rating",
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


def classify_match(stats: dict[str, Any], side: str) -> dict[str, float]:
    """Extract and return the feature vector for one side of a match.

    Args:
        stats: The raw stats dict from Match.stats_home or Match.stats_away.
        side: "home" or "away" — used to compute directness from pass sub-keys.

    Returns:
        Dict with keys matching FEATURE_COLS.
    """
    # TODO: implement — map API-Football stat labels to feature columns
    return {col: 0.0 for col in FEATURE_COLS}


async def build_feature_matrix(session: AsyncSession) -> pd.DataFrame:
    """Query all completed matches from the DB and build the full feature matrix.

    Returns a DataFrame with FEATURE_COLS plus metadata columns:
    match_id, team_id, season.
    """
    # TODO: implement — query Match, compute features per match per team
    return pd.DataFrame(columns=["match_id", "team_id", "season", *FEATURE_COLS])


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
