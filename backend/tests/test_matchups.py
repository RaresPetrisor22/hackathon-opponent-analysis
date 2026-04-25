"""Unit tests for analysis.matchups production configuration.

Pipeline under test:
  classify_match (per-match features) -> build_feature_matrix (DB → DF)
  -> aggregate_to_team_level -> ArchetypeClusterer (std + PCA + KMeans, k=4)

Run with:
    cd backend
    uv run pytest tests/test_matchups.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.matchups import (
    ARCHETYPE_DESCRIPTIONS,
    ARCHETYPE_LABELS,
    FEATURE_COLS,
    N_CLUSTERS,
    PCA_VARIANCE_THRESHOLD,
    ArchetypeClusterer,
    aggregate_to_team_level,
    build_feature_matrix,
    classify_match,
)
from app.db import Base
from app.models.archetype import Archetype  # noqa: F401  (register with metadata)
from app.models.match import Match
from app.models.player import Player  # noqa: F401
from app.models.team import Team


# ---------------------------------------------------------------------------
# classify_match — pure function, no DB
# ---------------------------------------------------------------------------

class TestClassifyMatch:
    def test_returns_all_feature_cols(self) -> None:
        out = classify_match({}, {})
        assert set(out.keys()) == set(FEATURE_COLS)

    def test_all_zero_when_no_data(self) -> None:
        out = classify_match({}, {})
        for col in FEATURE_COLS:
            assert out[col] == 0.0

    def test_basic_extraction(self) -> None:
        team = {
            "ball_possession": 60,
            "total_shots": 12,
            "shots_on_goal": 5,
            "shots_outsidebox": 4,
            "passes_pct": 85,
        }
        out = classify_match(team, {}, goals_for=2, goals_against=1)
        assert out["possession_pct"] == 60.0
        assert out["pass_accuracy"] == 85.0
        assert out["long_shot_ratio"] == pytest.approx(4 / 12)
        assert out["shot_quality"] == pytest.approx(5 / 12)
        assert out["goal_diff"] == 1.0

    def test_negative_goal_diff(self) -> None:
        out = classify_match({}, {}, goals_for=0, goals_against=3)
        assert out["goal_diff"] == -3.0

    def test_none_values_treated_as_zero(self) -> None:
        team = {
            "ball_possession": None,
            "total_shots": None,
            "shots_on_goal": None,
            "shots_outsidebox": None,
            "passes_pct": None,
        }
        out = classify_match(team, {}, goals_for=0, goals_against=0)
        for col in FEATURE_COLS:
            assert out[col] == 0.0

    def test_zero_shots_avoids_division_by_zero(self) -> None:
        team = {"total_shots": 0, "shots_outsidebox": 4}
        out = classify_match(team, {}, goals_for=1, goals_against=0)
        assert out["long_shot_ratio"] == 0.0
        assert out["shot_quality"] == 0.0

    def test_returns_floats_only(self) -> None:
        team = {"ball_possession": 50, "total_shots": 10, "passes_pct": 75}
        out = classify_match(team, {}, goals_for=1, goals_against=1)
        for v in out.values():
            assert isinstance(v, float)


# ---------------------------------------------------------------------------
# build_feature_matrix + aggregate_to_team_level — DB-backed
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


async def _team(session, api_id: int, name: str) -> Team:
    t = Team(api_football_id=api_id, name=name)
    session.add(t)
    await session.flush()
    return t


def _stats(possession=50, shots=10, on_goal=4, outside=4, pass_pct=80) -> dict:
    return {
        "ball_possession": possession,
        "total_shots": shots,
        "shots_on_goal": on_goal,
        "shots_outsidebox": outside,
        "passes_pct": pass_pct,
        "fouls": 10,
        "total_passes": 400,
    }


async def _match(
    session, *, fixture_id, home_id, away_id, home_score, away_score, date,
    home_stats=None, away_stats=None,
):
    m = Match(
        id=fixture_id,
        season_id=2024,
        league_id=283,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=home_score,
        away_score=away_score,
        date=date,
        status="FT",
        stats_home=home_stats or _stats(),
        stats_away=away_stats or _stats(),
    )
    session.add(m)
    await session.flush()
    return m


class TestBuildFeatureMatrix:
    async def test_empty_db(self, session) -> None:
        df = await build_feature_matrix(session)
        assert df.empty
        assert list(df.columns) == ["match_id", "team_id", "season", *FEATURE_COLS]

    async def test_one_match_yields_two_rows(self, session) -> None:
        a = await _team(session, 1, "A")
        b = await _team(session, 2, "B")
        await _match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            home_score=2, away_score=1,
            date=datetime(2025, 1, 10, tzinfo=timezone.utc),
        )
        df = await build_feature_matrix(session)
        assert len(df) == 2
        assert set(df["team_id"]) == {a.id, b.id}
        assert (df["match_id"] == 1).all()

        # Goal_diff signs should be opposites
        home_row = df[df["team_id"] == a.id].iloc[0]
        away_row = df[df["team_id"] == b.id].iloc[0]
        assert home_row["goal_diff"] == 1.0
        assert away_row["goal_diff"] == -1.0

    async def test_excludes_matches_without_stats(self, session) -> None:
        from sqlalchemy import null, update

        a = await _team(session, 1, "A")
        b = await _team(session, 2, "B")
        await _match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            home_score=1, away_score=0,
            date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        await _match(
            session, fixture_id=2, home_id=a.id, away_id=b.id,
            home_score=2, away_score=2,
            date=datetime(2025, 1, 8, tzinfo=timezone.utc),
        )
        # Force fixture 2 to SQL NULL stats (Match.complete() filters these)
        await session.execute(
            update(Match).where(Match.id == 2)
            .values(stats_home=null(), stats_away=null())
        )
        await session.flush()
        df = await build_feature_matrix(session)
        assert set(df["match_id"]) == {1}


class TestAggregateToTeamLevel:
    def test_empty_df_returns_empty_with_correct_cols(self) -> None:
        match_df = pd.DataFrame(columns=["match_id", "team_id", "season", *FEATURE_COLS])
        team_df = aggregate_to_team_level(match_df)
        assert team_df.empty
        assert "team_id" in team_df.columns
        for col in FEATURE_COLS:
            assert col in team_df.columns

    def test_means_are_computed_per_team(self) -> None:
        match_df = pd.DataFrame([
            {"match_id": 1, "team_id": 1, "season": 2024,
             "possession_pct": 60, "pass_accuracy": 80,
             "long_shot_ratio": 0.4, "shot_quality": 0.3, "goal_diff": 1.0},
            {"match_id": 2, "team_id": 1, "season": 2024,
             "possession_pct": 50, "pass_accuracy": 70,
             "long_shot_ratio": 0.5, "shot_quality": 0.4, "goal_diff": -1.0},
            {"match_id": 1, "team_id": 2, "season": 2024,
             "possession_pct": 40, "pass_accuracy": 75,
             "long_shot_ratio": 0.3, "shot_quality": 0.5, "goal_diff": 2.0},
        ])
        team_df = aggregate_to_team_level(match_df)
        assert len(team_df) == 2
        team1 = team_df[team_df["team_id"] == 1].iloc[0]
        assert team1["possession_pct"] == 55.0
        assert team1["goal_diff"] == 0.0


# ---------------------------------------------------------------------------
# ArchetypeClusterer — fit / predict / label
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_team_df() -> pd.DataFrame:
    """16 teams with structurally different feature profiles (4 archetypes)."""
    rng = np.random.default_rng(42)

    def cluster(n: int, centre: list[float], jitter: float = 1.0):
        rows = []
        for _ in range(n):
            row = [c + rng.normal(0, jitter * 0.05 * abs(c) if c else jitter * 0.05)
                   for c in centre]
            rows.append(row)
        return rows

    # 4 clusters, 4 teams each
    elite = cluster(4, [56.0, 80.0, 0.37, 0.36, 0.40])         # high goal_diff
    counter = cluster(4, [48.0, 76.0, 0.39, 0.35, 0.18])       # mid
    long_range = cluster(4, [50.0, 74.0, 0.42, 0.29, -0.07])   # high long_shot
    struggling = cluster(4, [45.0, 71.0, 0.48, 0.32, -0.44])   # low goal_diff

    rows = elite + counter + long_range + struggling
    df = pd.DataFrame(rows, columns=FEATURE_COLS)
    df.insert(0, "team_id", range(1, len(df) + 1))
    return df


class TestArchetypeClusterer:
    def test_fit_records_silhouette_and_centers(self, synthetic_team_df) -> None:
        c = ArchetypeClusterer()
        c.fit(synthetic_team_df)

        assert c.kmeans is not None
        assert c.pca is not None
        assert c.cluster_centers_pca_ is not None
        assert c.cluster_centers_original_ is not None
        assert c.silhouette_ is not None
        assert c.team_labels_ is not None

        # 4 clusters in 5-feature original space
        assert c.cluster_centers_original_.shape == (N_CLUSTERS, len(FEATURE_COLS))
        # Team labels — one per row
        assert len(c.team_labels_) == len(synthetic_team_df)
        # Silhouette in plausible range; well-separated synthetic data → > 0.3
        assert -1.0 <= c.silhouette_ <= 1.0
        assert c.silhouette_ > 0.3

    def test_pca_n_components_capped(self, synthetic_team_df) -> None:
        c = ArchetypeClusterer()
        c.fit(synthetic_team_df)
        # Must retain ≥ 2, ≤ 5 (number of features)
        assert 2 <= c.n_components_ <= len(FEATURE_COLS)

    def test_fit_raises_on_empty(self) -> None:
        c = ArchetypeClusterer()
        with pytest.raises(ValueError):
            c.fit(pd.DataFrame(columns=["team_id", *FEATURE_COLS]))

    def test_predict_before_fit_raises(self) -> None:
        c = ArchetypeClusterer()
        with pytest.raises(RuntimeError):
            c.predict({col: 0.0 for col in FEATURE_COLS})

    def test_predict_returns_valid_cluster_index(self, synthetic_team_df) -> None:
        c = ArchetypeClusterer()
        c.fit(synthetic_team_df)
        # Use the first team's actual feature values
        feats = synthetic_team_df.iloc[0][FEATURE_COLS].to_dict()
        pred = c.predict(feats)
        assert 0 <= pred < N_CLUSTERS

    def test_predict_recovers_training_label_for_known_team(
        self, synthetic_team_df,
    ) -> None:
        """Predict on a row used for training → must return the same cluster."""
        c = ArchetypeClusterer()
        c.fit(synthetic_team_df)
        for i in range(len(synthetic_team_df)):
            feats = synthetic_team_df.iloc[i][FEATURE_COLS].to_dict()
            pred = c.predict(feats)
            assert pred == int(c.team_labels_[i])

    def test_label_clusters_returns_known_labels(self, synthetic_team_df) -> None:
        c = ArchetypeClusterer()
        c.fit(synthetic_team_df)
        labels = c.label_clusters()
        assert len(labels) == N_CLUSTERS
        assert set(labels.values()).issubset(set(ARCHETYPE_LABELS))

    def test_label_clusters_assigns_elite_to_highest_goal_diff(
        self, synthetic_team_df,
    ) -> None:
        c = ArchetypeClusterer()
        c.fit(synthetic_team_df)
        labels = c.label_clusters()
        gd_idx = FEATURE_COLS.index("goal_diff")
        # Highest goal_diff cluster should be Dominant Possession Elite
        elite_cluster = int(np.argmax(c.cluster_centers_original_[:, gd_idx]))
        assert labels[elite_cluster] == "Dominant Possession Elite"

    def test_label_clusters_assigns_struggling_to_lowest_goal_diff(
        self, synthetic_team_df,
    ) -> None:
        c = ArchetypeClusterer()
        c.fit(synthetic_team_df)
        labels = c.label_clusters()
        gd_idx = FEATURE_COLS.index("goal_diff")
        struggling_cluster = int(np.argmin(c.cluster_centers_original_[:, gd_idx]))
        assert labels[struggling_cluster] == "Defensive / Low Output"


# ---------------------------------------------------------------------------
# Sanity checks on production constants
# ---------------------------------------------------------------------------

class TestProductionConstants:
    def test_n_clusters_is_4(self) -> None:
        assert N_CLUSTERS == 4

    def test_feature_cols_count(self) -> None:
        assert len(FEATURE_COLS) == 5
        # Required production features
        for c in ("possession_pct", "pass_accuracy", "long_shot_ratio",
                  "shot_quality", "goal_diff"):
            assert c in FEATURE_COLS

    def test_pca_threshold_is_reasonable(self) -> None:
        assert 0.80 <= PCA_VARIANCE_THRESHOLD <= 0.99

    def test_archetype_labels_match_descriptions(self) -> None:
        assert len(ARCHETYPE_LABELS) == N_CLUSTERS
        for label in ARCHETYPE_LABELS:
            assert label in ARCHETYPE_DESCRIPTIONS
            assert len(ARCHETYPE_DESCRIPTIONS[label]) > 20  # non-trivial description
