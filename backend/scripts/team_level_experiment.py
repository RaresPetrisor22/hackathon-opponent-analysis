"""team_level_experiment.py — Cluster TEAMS, not match-rows.

Hypothesis: averaging each team's matches into a single feature vector should
produce a much higher silhouette score, because we collapse the "good day vs
bad day" within-team noise that's dominating the match-level clustering.

Tradeoff: the SuperLiga has only 16 teams, so the sample size becomes tiny.
We score a smaller k range (2..6) and inspect the actual team-to-cluster
assignments — eyeball is the real validation here, not silhouette alone.

Run:
    cd backend
    uv run python scripts/team_level_experiment.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from app.analysis.matchups import FEATURE_COLS, build_feature_matrix
from app.db import AsyncSessionLocal, init_db
from app.models.team import Team

K_RANGE = range(2, 7)


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        # Match-level matrix (current production output)
        match_df = await build_feature_matrix(session)
        # Team name lookup
        teams = {t.id: t.name for t in (await session.execute(select(Team))).scalars()}

    print(f"Match-level rows: {len(match_df)} ({match_df['team_id'].nunique()} teams)")
    if match_df.empty:
        print("No data — run ingest_season.py first.")
        return

    # ----------------------------------------------------------------------
    # Aggregate to team level: mean of each feature across the team's season
    # ----------------------------------------------------------------------
    team_df = (
        match_df.groupby("team_id")[FEATURE_COLS]
        .mean()
        .reset_index()
    )
    team_df["team_name"] = team_df["team_id"].map(teams)
    team_df = team_df[["team_id", "team_name", *FEATURE_COLS]]
    print(f"Team-level rows: {len(team_df)}\n")

    # ----------------------------------------------------------------------
    # Reference: match-level silhouette (production baseline)
    # ----------------------------------------------------------------------
    print("=" * 72)
    print("REFERENCE — match-level (current production approach)")
    print("=" * 72)
    X_match = StandardScaler().fit_transform(match_df[FEATURE_COLS].values)
    print("  k | silhouette")
    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_match)
        print(f"  {k} | {silhouette_score(X_match, labels):10.4f}")

    # ----------------------------------------------------------------------
    # Team-level silhouette
    # ----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("EXPERIMENT — team-level (mean across each team's matches)")
    print("=" * 72)
    scaler_team = StandardScaler().fit(team_df[FEATURE_COLS].values)
    X_team = scaler_team.transform(team_df[FEATURE_COLS].values)

    print("  k | silhouette |  inertia")
    print("----+------------+----------")
    scores: dict[int, float] = {}
    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_team)
        sil = silhouette_score(X_team, labels)
        scores[k] = sil
        print(f"  {k} | {sil:10.4f} | {km.inertia_:8.2f}")

    best_k = max(scores, key=lambda k: scores[k])
    print(f"\n-> best k = {best_k} (silhouette = {scores[best_k]:.4f})")

    # ----------------------------------------------------------------------
    # Show actual team-to-cluster assignments for best k AND k=5 (product)
    # ----------------------------------------------------------------------
    for k_show in sorted({best_k, 5}):
        if k_show not in K_RANGE:
            continue
        print("\n" + "-" * 72)
        print(f"Team assignments at k={k_show}:")
        print("-" * 72)
        km = KMeans(n_clusters=k_show, random_state=42, n_init=10)
        labels = km.fit_predict(X_team)
        centers = scaler_team.inverse_transform(km.cluster_centers_)

        # Print centroids
        print("\nCentroids (original feature units):")
        header = "cluster | " + " | ".join(f"{c[:14]:>14}" for c in FEATURE_COLS) + " | n"
        print(header)
        print("-" * len(header))
        for ci in range(k_show):
            cells = " | ".join(f"{v:14.2f}" for v in centers[ci])
            n = int(np.sum(labels == ci))
            print(f"   {ci}    | {cells} | {n}")

        # Print which teams ended up in which cluster
        print("\nTeams per cluster:")
        for ci in range(k_show):
            members = team_df.loc[labels == ci, "team_name"].tolist()
            print(f"  cluster {ci}: {', '.join(members)}")


if __name__ == "__main__":
    asyncio.run(main())
