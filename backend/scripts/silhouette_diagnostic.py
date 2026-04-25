"""silhouette_diagnostic.py — Find the best k for KMeans archetypes.

Builds the feature matrix from the real DB, then for each k in K_RANGE:
  - fits KMeans on standardised features
  - computes silhouette score (higher = tighter, better-separated clusters)
  - computes inertia (within-cluster sum of squares — for elbow check)

Prints a table and the recommended k.

Usage:
    cd backend
    uv run python scripts/silhouette_diagnostic.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.analysis.matchups import FEATURE_COLS, build_feature_matrix
from app.db import AsyncSessionLocal, init_db

K_RANGE = range(2, 11)


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        df = await build_feature_matrix(session)

    print(f"Feature matrix: {len(df)} rows ({df['team_id'].nunique()} teams, "
          f"{df['match_id'].nunique()} matches)")
    if df.empty:
        print("No data — run ingest_season.py first.")
        return

    X = StandardScaler().fit_transform(df[FEATURE_COLS].values)

    print("\n  k | silhouette |  inertia | gap_to_prev")
    print("----+------------+----------+------------")

    prev_inertia: float | None = None
    rows: list[tuple[int, float, float]] = []
    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        sil = silhouette_score(X, labels)
        inertia = km.inertia_
        rows.append((k, sil, inertia))
        gap = "" if prev_inertia is None else f"{prev_inertia - inertia:8.2f}"
        print(f"  {k:1d} | {sil:10.4f} | {inertia:8.2f} | {gap}")
        prev_inertia = inertia

    best_k_sil = max(rows, key=lambda r: r[1])[0]
    print(f"\nHighest silhouette: k={best_k_sil}")

    # Print centroids for the recommended k (in original feature units)
    print(f"\nCentroids for k={best_k_sil} (original feature units):")
    scaler = StandardScaler().fit(df[FEATURE_COLS].values)
    km = KMeans(n_clusters=best_k_sil, random_state=42, n_init=10)
    km.fit(scaler.transform(df[FEATURE_COLS].values))
    centers = scaler.inverse_transform(km.cluster_centers_)
    header = "cluster | " + " | ".join(f"{c[:14]:>14}" for c in FEATURE_COLS)
    print(header)
    print("-" * len(header))
    for i, row in enumerate(centers):
        cells = " | ".join(f"{v:14.2f}" for v in row)
        size = int(np.sum(km.labels_ == i))
        print(f"   {i}    | {cells}   (n={size})")


if __name__ == "__main__":
    asyncio.run(main())
