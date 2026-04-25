"""End-to-end integration test for the production matchup pipeline.

Exercises every component the dossier route depends on, in the same order it
will run live:

  1. Seed an in-memory SQLite DB with 8 teams + their head-to-head matches
     (each team plays each other once → 28 matches, 56 team-match rows).
  2. build_feature_matrix         (DB → match-level DataFrame)
  3. aggregate_to_team_level      (match → team-level DataFrame)
  4. ArchetypeClusterer.fit       (std + PCA + KMeans, k=4)
  5. ArchetypeClusterer.label_clusters  (heuristic labelling)
  6. Persist Archetype rows + stamp Match.home_archetype_id / away_archetype_id
  7. get_team_record_vs_archetypes  (per-opponent W/D/L breakdown)
  8. predict_matchup                (top-level dossier entry point)

Each step's contract is verified — types, schema fields, foreign-key
consistency — and the output of each step is fed into the next.

Run with:
    cd backend
    uv run pytest tests/test_integration_dossier.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.matchups import (
    ARCHETYPE_DESCRIPTIONS,
    ARCHETYPE_LABELS,
    FEATURE_COLS,
    N_CLUSTERS,
    ArchetypeClusterer,
    aggregate_to_team_level,
    build_feature_matrix,
    classify_match,
    get_team_record_vs_archetypes,
    predict_matchup,
)
from app.db import Base
from app.models.archetype import Archetype
from app.models.match import Match
from app.models.player import Player  # noqa: F401  (register with metadata)
from app.models.team import Team
from app.schemas.dossier import ArchetypeRecord, MatchupSection


# ---------------------------------------------------------------------------
# Test fixtures: synthetic 8-team league with 4 stylistic archetypes.
# Each archetype contains 2 teams, so cluster sizes and team-archetype
# membership are predictable.
# ---------------------------------------------------------------------------

# (api_id, name, archetype intent → centroid signature)
TEAM_PROFILES = [
    # Dominant Possession Elite (high possession, high pass acc, win-leaning)
    (101, "Elite_A", {"possession": 60, "pass_pct": 84, "shots": 14,
                      "on_goal": 6, "outside": 4, "win_bias": 1.6}),
    (102, "Elite_B", {"possession": 58, "pass_pct": 82, "shots": 13,
                      "on_goal": 5, "outside": 4, "win_bias": 1.4}),
    # Compact Counter (mid possession, balanced, neutral results)
    (103, "Counter_A", {"possession": 49, "pass_pct": 76, "shots": 11,
                        "on_goal": 4, "outside": 4, "win_bias": 0.2}),
    (104, "Counter_B", {"possession": 47, "pass_pct": 75, "shots": 10,
                        "on_goal": 4, "outside": 4, "win_bias": 0.0}),
    # Long-Range Specialists (high long_shot_ratio, low shot_quality)
    (105, "LongShot_A", {"possession": 50, "pass_pct": 73, "shots": 12,
                         "on_goal": 3, "outside": 7, "win_bias": -0.1}),
    (106, "LongShot_B", {"possession": 52, "pass_pct": 74, "shots": 13,
                         "on_goal": 3, "outside": 8, "win_bias": 0.0}),
    # Direct & Struggling (low possession, low pass acc, lose-leaning)
    (107, "Strug_A", {"possession": 45, "pass_pct": 70, "shots": 9,
                      "on_goal": 3, "outside": 5, "win_bias": -1.4}),
    (108, "Strug_B", {"possession": 44, "pass_pct": 69, "shots": 8,
                      "on_goal": 2, "outside": 5, "win_bias": -1.6}),
]


@pytest_asyncio.fixture
async def session():
    """Fresh in-memory SQLite per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(session):
    """Seed 8 teams + a full round-robin (28 matches) with stat profiles
    matching their intended archetype.
    """
    rng = np.random.default_rng(7)

    # Insert teams
    teams: dict[int, Team] = {}
    for api_id, name, _profile in TEAM_PROFILES:
        t = Team(api_football_id=api_id, name=name)
        session.add(t)
        await session.flush()
        teams[api_id] = t
    await session.commit()

    profile_lookup = {api_id: prof for api_id, _, prof in TEAM_PROFILES}

    def stats_for(profile: dict) -> dict:
        """Generate one match's stats with mild noise around the profile."""
        return {
            "ball_possession": profile["possession"] + rng.normal(0, 1.5),
            "total_shots": max(1, int(profile["shots"] + rng.normal(0, 1))),
            "shots_on_goal": max(0, int(profile["on_goal"] + rng.normal(0, 0.7))),
            "shots_outsidebox": max(0, int(profile["outside"] + rng.normal(0, 0.7))),
            "passes_pct": profile["pass_pct"] + rng.normal(0, 1.2),
            "fouls": 10,
            "total_passes": 400,
        }

    def goals_for(home_profile: dict, away_profile: dict) -> tuple[int, int]:
        """Goals influenced by each team's win_bias (centred near 1.5 GF)."""
        h = max(0, int(round(1.4 + home_profile["win_bias"] * 0.5
                             + rng.normal(0, 0.5))))
        a = max(0, int(round(1.4 + away_profile["win_bias"] * 0.5
                             + rng.normal(0, 0.5))))
        # Mild home advantage
        if h == a and rng.random() < 0.3:
            h += 1
        return h, a

    # Single round-robin: 8 teams → C(8,2) = 28 matches
    api_ids = list(profile_lookup.keys())
    fixture_id = 1
    base_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(len(api_ids)):
        for j in range(i + 1, len(api_ids)):
            home_api = api_ids[i]
            away_api = api_ids[j]
            hp = profile_lookup[home_api]
            ap = profile_lookup[away_api]
            gh, ga = goals_for(hp, ap)
            m = Match(
                id=fixture_id,
                season_id=2024,
                league_id=283,
                home_team_id=teams[home_api].id,
                away_team_id=teams[away_api].id,
                home_score=gh,
                away_score=ga,
                date=base_date + timedelta(days=fixture_id),
                status="FT",
                stats_home=stats_for(hp),
                stats_away=stats_for(ap),
            )
            session.add(m)
            fixture_id += 1
    await session.commit()

    return {"session": session, "teams": teams, "profiles": profile_lookup}


# ---------------------------------------------------------------------------
# Step-by-step pipeline integration tests
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """Each test progressively exercises one more pipeline stage on the
    same seeded DB. Failures pinpoint the first broken stage."""

    async def test_step1_db_has_seeded_data(self, seeded_db) -> None:
        s = seeded_db["session"]
        teams = (await s.execute(select(Team))).scalars().all()
        matches = (await s.execute(select(Match))).scalars().all()
        assert len(teams) == 8
        assert len(matches) == 28

    async def test_step2_build_feature_matrix(self, seeded_db) -> None:
        s = seeded_db["session"]
        df = await build_feature_matrix(s)
        # 28 matches × 2 teams per match = 56 rows
        assert len(df) == 56
        # All FEATURE_COLS present and numeric
        for col in FEATURE_COLS:
            assert col in df.columns
            assert df[col].dtype.kind in "fi"
        # Each team appears in many matches (7 home + 7 away across 8 teams)
        assert df["team_id"].nunique() == 8

    async def test_step3_team_level_aggregation(self, seeded_db) -> None:
        s = seeded_db["session"]
        match_df = await build_feature_matrix(s)
        team_df = aggregate_to_team_level(match_df)
        assert len(team_df) == 8
        assert set(team_df.columns) == {"team_id", *FEATURE_COLS}

    async def test_step4_clusterer_fit(self, seeded_db) -> None:
        s = seeded_db["session"]
        team_df = aggregate_to_team_level(await build_feature_matrix(s))
        c = ArchetypeClusterer()
        c.fit(team_df)
        assert c.silhouette_ is not None
        # On well-separated synthetic data, silhouette must be reasonable
        assert c.silhouette_ > 0.25
        assert c.cluster_centers_original_.shape == (N_CLUSTERS, len(FEATURE_COLS))

    async def test_step5_label_clusters_uses_real_archetype_names(
        self, seeded_db,
    ) -> None:
        s = seeded_db["session"]
        team_df = aggregate_to_team_level(await build_feature_matrix(s))
        c = ArchetypeClusterer()
        c.fit(team_df)
        labels = c.label_clusters()
        assert len(labels) == N_CLUSTERS
        # All labels must come from the canonical list
        for label in labels.values():
            assert label in ARCHETYPE_LABELS

    async def test_step6_persist_archetypes_and_stamp_matches(
        self, seeded_db,
    ) -> None:
        """Replicates what build_archetypes.py does: upsert Archetype rows
        and set Match.home_archetype_id / away_archetype_id."""
        s = seeded_db["session"]
        match_df = await build_feature_matrix(s)
        team_df = aggregate_to_team_level(match_df)

        c = ArchetypeClusterer()
        c.fit(team_df)
        labels = c.label_clusters()

        # Upsert archetypes
        cluster_to_arch_id: dict[int, int] = {}
        for ci in range(N_CLUSTERS):
            arch = Archetype(
                name=labels[ci],
                description=ARCHETYPE_DESCRIPTIONS[labels[ci]],
                cluster_center=c.cluster_centers_original_[ci].tolist(),
                assigned_match_ids=[],
            )
            s.add(arch)
            await s.flush()
            cluster_to_arch_id[ci] = arch.id

        # Map team_id -> archetype_id
        team_to_arch: dict[int, int] = {}
        for i, row in team_df.iterrows():
            tid = int(row["team_id"])
            cluster_idx = int(c.team_labels_[i])
            team_to_arch[tid] = cluster_to_arch_id[cluster_idx]

        # Stamp every match
        all_matches = (await s.execute(select(Match))).scalars().all()
        for m in all_matches:
            m.home_archetype_id = team_to_arch[m.home_team_id]
            m.away_archetype_id = team_to_arch[m.away_team_id]
        await s.commit()

        # Verify persistence
        n_archetypes = len((await s.execute(select(Archetype))).scalars().all())
        stamped = (await s.execute(
            select(Match).where(Match.home_archetype_id.is_not(None))
        )).scalars().all()
        assert n_archetypes == N_CLUSTERS
        assert len(stamped) == 28  # all matches stamped

    async def test_step7_get_team_record_vs_archetypes(self, seeded_db) -> None:
        """Run the full pipeline + verify per-opponent W/D/L sums correctly."""
        s = seeded_db["session"]
        teams = seeded_db["teams"]

        # Run pipeline through stamping (re-use logic from previous test)
        match_df = await build_feature_matrix(s)
        team_df = aggregate_to_team_level(match_df)
        c = ArchetypeClusterer()
        c.fit(team_df)
        labels = c.label_clusters()
        cluster_to_arch_id: dict[int, int] = {}
        for ci in range(N_CLUSTERS):
            arch = Archetype(
                name=labels[ci],
                description=ARCHETYPE_DESCRIPTIONS[labels[ci]],
                cluster_center=c.cluster_centers_original_[ci].tolist(),
            )
            s.add(arch)
            await s.flush()
            cluster_to_arch_id[ci] = arch.id
        team_to_arch = {
            int(team_df.iloc[i]["team_id"]): cluster_to_arch_id[int(c.team_labels_[i])]
            for i in range(len(team_df))
        }
        for m in (await s.execute(select(Match))).scalars().all():
            m.home_archetype_id = team_to_arch[m.home_team_id]
            m.away_archetype_id = team_to_arch[m.away_team_id]
        await s.commit()

        # Pick the first team and get their record
        target_team = teams[101]  # Elite_A
        records = await get_team_record_vs_archetypes(target_team.id, s)

        # 4 archetypes → 4 records (some may have 0 matches if team's own
        # archetype has only 1 other member — opponents are the other 7 teams)
        assert len(records) == N_CLUSTERS
        for r in records:
            assert isinstance(r, ArchetypeRecord)
            assert r.matches_played == r.wins + r.draws + r.losses
            assert r.goals_for >= 0
            assert r.goals_against >= 0

        # Total matches across all archetypes should equal 7 (round-robin)
        total = sum(r.matches_played for r in records)
        assert total == 7

    async def test_step8_predict_matchup_full_dossier(self, seeded_db) -> None:
        """End-to-end: predict_matchup returns a valid MatchupSection."""
        s = seeded_db["session"]
        teams = seeded_db["teams"]

        # Run pipeline through stamping
        match_df = await build_feature_matrix(s)
        team_df = aggregate_to_team_level(match_df)
        c = ArchetypeClusterer()
        c.fit(team_df)
        labels = c.label_clusters()
        cluster_to_arch_id: dict[int, int] = {}
        for ci in range(N_CLUSTERS):
            arch = Archetype(
                name=labels[ci],
                description=ARCHETYPE_DESCRIPTIONS[labels[ci]],
                cluster_center=c.cluster_centers_original_[ci].tolist(),
            )
            s.add(arch)
            await s.flush()
            cluster_to_arch_id[ci] = arch.id
        team_to_arch = {
            int(team_df.iloc[i]["team_id"]): cluster_to_arch_id[int(c.team_labels_[i])]
            for i in range(len(team_df))
        }
        for m in (await s.execute(select(Match))).scalars().all():
            m.home_archetype_id = team_to_arch[m.home_team_id]
            m.away_archetype_id = team_to_arch[m.away_team_id]
        await s.commit()

        # Use Elite_A (api_id=101) as FCU stand-in, predict vs Strug_A (107)
        fcu_api_id = 101
        opponent = teams[107]

        section = await predict_matchup(
            opponent_id=opponent.id,
            fcu_api_football_id=fcu_api_id,
            session=s,
        )
        assert isinstance(section, MatchupSection)
        # FCU's archetype must be one of the canonical labels
        assert section.fcu_archetype_name in ARCHETYPE_LABELS
        assert section.fcu_archetype_id != 0
        assert section.archetypes  # non-empty
        assert len(section.archetypes) == N_CLUSTERS
        # Summary string must mention the archetype name (not be the stub)
        assert "FC U Cluj" in section.prediction_summary
        assert section.fcu_archetype_name in section.prediction_summary
        assert "Run 'uv run python scripts/build_archetypes.py'" not in section.prediction_summary


# ---------------------------------------------------------------------------
# Graceful-degradation tests: pipeline should not crash if archetypes missing.
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    async def test_predict_matchup_returns_stub_if_no_archetypes(
        self, seeded_db,
    ) -> None:
        """If build_archetypes.py hasn't been run, predict_matchup must
        return a graceful stub instead of raising."""
        s = seeded_db["session"]
        teams = seeded_db["teams"]

        section = await predict_matchup(
            opponent_id=teams[101].id,
            fcu_api_football_id=102,
            session=s,
        )
        assert isinstance(section, MatchupSection)
        assert section.fcu_archetype_id == 0
        assert section.fcu_archetype_name == "Unknown"
        assert section.archetypes == []
        assert "build_archetypes.py" in section.prediction_summary

    async def test_get_team_record_with_no_archetypes_returns_empty(
        self, seeded_db,
    ) -> None:
        s = seeded_db["session"]
        records = await get_team_record_vs_archetypes(
            seeded_db["teams"][101].id, s
        )
        assert records == []


# ---------------------------------------------------------------------------
# Schema validation: cluster_center round-trip from DB matches model output.
# ---------------------------------------------------------------------------

class TestSchemaConsistency:
    async def test_cluster_centers_persist_correctly(self, seeded_db) -> None:
        """Centroid stored as JSON list must be readable back as a list of floats
        with the same length as FEATURE_COLS."""
        s = seeded_db["session"]
        match_df = await build_feature_matrix(s)
        team_df = aggregate_to_team_level(match_df)
        c = ArchetypeClusterer()
        c.fit(team_df)

        arch = Archetype(
            name="TestArch",
            description="x",
            cluster_center=c.cluster_centers_original_[0].tolist(),
        )
        s.add(arch)
        await s.commit()

        loaded = (await s.execute(
            select(Archetype).where(Archetype.name == "TestArch")
        )).scalar_one()
        assert isinstance(loaded.cluster_center, list)
        assert len(loaded.cluster_center) == len(FEATURE_COLS)
        for v in loaded.cluster_center:
            assert isinstance(v, (int, float))
