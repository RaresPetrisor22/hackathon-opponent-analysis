from __future__ import annotations

"""Matchup Intelligence — the hero feature.

Production configuration (silhouette ≈ 0.446 at k=4 on the 2024-25 season):

  Pipeline      : per-team mean across season -> StandardScaler -> PCA(>= 90% var)
                  -> KMeans(k=4)
  Feature set   : possession_pct, pass_accuracy, long_shot_ratio, shot_quality,
                  goal_diff
                  Selected from a six-experiment sweep (see
                  scripts/team_silhouette_sweep.py). PCA reduction denoises the
                  16-team matrix and lifted silhouette from 0.295 -> 0.446.

  Why team-level: at match level (620 rows), within-team match-to-match noise
                  dominated the cluster centroids. Aggregating to the 16
                  teams collapses that noise and surfaces stylistic structure.

  Why these features: 'possession_pct' + 'pass_accuracy' capture build-up
                  quality; 'long_shot_ratio' and 'shot_quality' capture shot
                  selection style; 'goal_diff' carries outcome signal that a
                  pure stats vector misses (a 60% possession + 0 GD team is
                  meaningfully different from a 60% possession + 1.5 GD team).

Each match's home_archetype_id / away_archetype_id is set to the archetype of
the home/away team — i.e. archetypes are a TEAM property that propagates to
every match they play. This keeps the W/D/L breakdown in
`get_team_record_vs_archetypes` consistent: when you ask "how does X do vs
Direct & Struggling teams?" the answer is computed over X's matches against
every team in that archetype.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.archetype import Archetype
from app.models.match import Match
from app.models.team import Team
from app.schemas.dossier import ArchetypeRecord, MatchupSection

FEATURE_COLS = [
    "possession_pct",
    "pass_accuracy",
    "long_shot_ratio",
    "shot_quality",
    "goal_diff",
]

N_CLUSTERS = 4

# PCA retains at least this fraction of standardised variance before clustering.
PCA_VARIANCE_THRESHOLD = 0.90

# Cluster labels — assigned by `ArchetypeClusterer.label_clusters()` from the
# observed centroid signatures (see scripts/team_clustering_outcome_style.py).
ARCHETYPE_LABELS = [
    "Dominant Possession Elite",
    "Compact Counter",
    "Long-Range Specialists",
    "Direct & Struggling",
]

ARCHETYPE_DESCRIPTIONS: dict[str, str] = {
    "Dominant Possession Elite": (
        "High possession, high pass accuracy, positive goal differential. "
        "Imposes its rhythm on opponents and out-passes them in build-up. "
        "Big-Four profile in the 2024-25 SuperLiga."
    ),
    "Compact Counter": (
        "Mid-range possession, decent pass accuracy, neutral-to-positive goal "
        "differential. Pragmatic teams that absorb pressure and break "
        "efficiently — middle-of-the-table operators."
    ),
    "Long-Range Specialists": (
        "Elevated long-shot ratio with low shot quality. Outshoots opponents "
        "from distance but converts poorly — speculative attacking pattern."
    ),
    "Direct & Struggling": (
        "Low possession, low pass accuracy, negative goal differential. "
        "Bypasses midfield with direct play but lacks the quality to "
        "convert chances. Lower-table profile."
    ),
}


# ---------------------------------------------------------------------------
# Stat helpers
# ---------------------------------------------------------------------------

def _stat(d: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Read a numeric stat. Treat missing keys / None values as `default`."""
    v = d.get(key) if d else None
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def classify_match(
    team_stats: dict[str, Any],
    opp_stats: dict[str, Any],
    goals_for: int = 0,
    goals_against: int = 0,
) -> dict[str, float]:
    """Extract a single team's per-match feature vector.

    Args:
        team_stats: stats_home or stats_away for the team being classified.
        opp_stats:  the opposing team's stats from the same match (kept for
                    backwards-compat — not used by the production features but
                    callers may still need it for ad-hoc analysis).
        goals_for:  this team's goals in the match.
        goals_against: opposing team's goals in the match.

    Returns:
        Dict with keys == FEATURE_COLS.
    """
    ts = _stat(team_stats, "total_shots")

    return {
        "possession_pct": _stat(team_stats, "ball_possession"),
        "pass_accuracy": _stat(team_stats, "passes_pct"),
        "long_shot_ratio": _stat(team_stats, "shots_outsidebox") / ts if ts else 0.0,
        "shot_quality": _stat(team_stats, "shots_on_goal") / ts if ts else 0.0,
        "goal_diff": float(goals_for - goals_against),
    }


# ---------------------------------------------------------------------------
# Feature matrix builders
# ---------------------------------------------------------------------------

async def build_feature_matrix(session: AsyncSession) -> pd.DataFrame:
    """Match-level feature matrix. Two rows per match (one per team).

    Columns: match_id, team_id, season, *FEATURE_COLS.
    """
    stmt = select(Match).where(Match.complete())
    matches = list((await session.execute(stmt)).scalars().all())

    columns = ["match_id", "team_id", "season", *FEATURE_COLS]
    if not matches:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for m in matches:
        hs = m.stats_home or {}
        as_ = m.stats_away or {}
        gh = int(m.home_score or 0)
        ga = int(m.away_score or 0)

        rows.append({
            "match_id": m.id,
            "team_id": m.home_team_id,
            "season": m.season_id,
            **classify_match(hs, as_, gh, ga),
        })
        rows.append({
            "match_id": m.id,
            "team_id": m.away_team_id,
            "season": m.season_id,
            **classify_match(as_, hs, ga, gh),
        })

    return pd.DataFrame(rows, columns=columns)


def aggregate_to_team_level(match_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-match rows into one row per team (mean of each feature).

    Returns: DataFrame with columns [team_id, *FEATURE_COLS], one row per team.
    """
    if match_df.empty:
        return pd.DataFrame(columns=["team_id", *FEATURE_COLS])
    return (
        match_df.groupby("team_id")[FEATURE_COLS]
        .mean()
        .reset_index()
    )


# ---------------------------------------------------------------------------
# ArchetypeClusterer — production pipeline (std + PCA + KMeans)
# ---------------------------------------------------------------------------

class ArchetypeClusterer:
    """Production pipeline: StandardScaler -> PCA(>= 90% var) -> KMeans(k=4).

    Fitted on team-level data (mean of each team's matches). Stores the full
    pipeline so it can `predict()` on a new feature dict (e.g. FCU's mean
    vector) by applying the same scaler+PCA before nearest-cluster lookup.

    `cluster_centers_original_` is the per-cluster mean of member teams in the
    original (un-scaled) feature space. This is what gets persisted as
    `Archetype.cluster_center` for runtime distance comparisons.
    """

    def __init__(self) -> None:
        self.scaler: StandardScaler = StandardScaler()
        self.pca: PCA | None = None
        self.kmeans: KMeans | None = None

        # Cluster centroids in PCA-reduced space (used by predict()).
        self.cluster_centers_pca_: np.ndarray | None = None
        # Cluster centroids in original feature space (membership-mean — what
        # gets persisted to the DB and used for FCU nearest-archetype lookup).
        self.cluster_centers_original_: np.ndarray | None = None
        # Silhouette score on the team-level training data.
        self.silhouette_: float | None = None
        # Per-team cluster labels assigned during fit (aligned with the input
        # team_df row order).
        self.team_labels_: np.ndarray | None = None
        # Number of PCA components actually retained.
        self.n_components_: int | None = None

    def fit(self, team_df: pd.DataFrame) -> None:
        """Fit the full pipeline on the team-level feature matrix.

        Args:
            team_df: DataFrame with FEATURE_COLS, one row per team.
                     `team_id` column is allowed but ignored here.
        """
        if team_df.empty:
            raise ValueError("Cannot fit clusterer on empty team_df.")

        X_raw = team_df[FEATURE_COLS].fillna(0).values

        X_std = self.scaler.fit_transform(X_raw)

        # Pick smallest n_components reaching the variance threshold.
        full = PCA(random_state=42).fit(X_std)
        cum = np.cumsum(full.explained_variance_ratio_)
        n_components = int(np.searchsorted(cum, PCA_VARIANCE_THRESHOLD)) + 1
        n_components = max(2, min(n_components, X_std.shape[1]))
        self.n_components_ = n_components

        self.pca = PCA(n_components=n_components, random_state=42)
        X_pca = self.pca.fit_transform(X_std)

        self.kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=20)
        labels = self.kmeans.fit_predict(X_pca)

        self.cluster_centers_pca_ = self.kmeans.cluster_centers_.copy()
        self.team_labels_ = labels
        self.silhouette_ = float(silhouette_score(X_pca, labels))

        # Membership-mean centroids in original feature space (interpretable
        # and what we persist as Archetype.cluster_center).
        centers_original = np.zeros((N_CLUSTERS, len(FEATURE_COLS)), dtype=float)
        for ci in range(N_CLUSTERS):
            mask = labels == ci
            if mask.any():
                centers_original[ci] = X_raw[mask].mean(axis=0)
        self.cluster_centers_original_ = centers_original

    def predict(self, features: dict[str, float]) -> int:
        """Predict the cluster index for a single team-level feature dict."""
        if self.kmeans is None or self.pca is None:
            raise RuntimeError("Clusterer not fitted yet — call fit() first.")
        vec = np.array([[features.get(c, 0.0) for c in FEATURE_COLS]])
        X_std = self.scaler.transform(vec)
        X_pca = self.pca.transform(X_std)
        return int(self.kmeans.predict(X_pca)[0])

    def label_clusters(self) -> dict[int, str]:
        """Assign human-readable labels to clusters using the original-space centroids.

        Heuristic priority:
          1. Highest goal_diff + highest pass_accuracy -> Dominant Possession Elite
          2. Lowest goal_diff + low pass_accuracy      -> Direct & Struggling
          3. Highest long_shot_ratio (remaining)       -> Long-Range Specialists
          4. Whatever remains                          -> Compact Counter
        """
        if self.cluster_centers_original_ is None:
            return {i: ARCHETYPE_LABELS[i] for i in range(N_CLUSTERS)}

        centers = self.cluster_centers_original_  # shape (N_CLUSTERS, 5)
        idx = {c: i for i, c in enumerate(FEATURE_COLS)}

        gd = centers[:, idx["goal_diff"]]
        pacc = centers[:, idx["pass_accuracy"]]
        lsr = centers[:, idx["long_shot_ratio"]]

        result: dict[int, str] = {}
        assigned: set[int] = set()

        # Priority 1: highest goal_diff
        elite = int(np.argmax(gd))
        result[elite] = "Dominant Possession Elite"
        assigned.add(elite)

        # Priority 2: lowest goal_diff among remaining
        remaining = [i for i in range(N_CLUSTERS) if i not in assigned]
        struggling = remaining[int(np.argmin(gd[remaining]))]
        result[struggling] = "Direct & Struggling"
        assigned.add(struggling)

        # Priority 3: highest long_shot_ratio among remaining
        remaining = [i for i in range(N_CLUSTERS) if i not in assigned]
        if remaining:
            long_range = remaining[int(np.argmax(lsr[remaining]))]
            result[long_range] = "Long-Range Specialists"
            assigned.add(long_range)

        # Priority 4: whatever's left
        for i in range(N_CLUSTERS):
            if i not in assigned:
                result[i] = "Compact Counter"
                assigned.add(i)

        return result


# ---------------------------------------------------------------------------
# Per-opponent archetype record
# ---------------------------------------------------------------------------

async def get_team_record_vs_archetypes(
    team_id: int,
    session: AsyncSession,
) -> list[ArchetypeRecord]:
    """Return the team's W/D/L record broken down by the OPPONENT's archetype.

    For each archetype, the question is: when this team faced a side playing
    *that* style, what was their record?
    """
    archetypes = list((await session.execute(select(Archetype))).scalars().all())
    if not archetypes:
        return []

    stmt = (
        select(Match)
        .where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
            Match.status == "FT",
            or_(
                Match.home_archetype_id.is_not(None),
                Match.away_archetype_id.is_not(None),
            ),
        )
    )
    matches = list((await session.execute(stmt)).scalars().all())

    records: list[ArchetypeRecord] = []
    for arch in archetypes:
        wins = draws = losses = 0
        gf_list: list[int] = []
        ga_list: list[int] = []

        for m in matches:
            is_home = m.home_team_id == team_id
            opp_arch_id = m.away_archetype_id if is_home else m.home_archetype_id
            if opp_arch_id != arch.id:
                continue

            gf = int((m.home_score if is_home else m.away_score) or 0)
            ga = int((m.away_score if is_home else m.home_score) or 0)
            gf_list.append(gf)
            ga_list.append(ga)

            if gf > ga:
                wins += 1
            elif gf == ga:
                draws += 1
            else:
                losses += 1

        played = wins + draws + losses
        records.append(
            ArchetypeRecord(
                archetype_id=arch.id,
                archetype_name=arch.name,
                archetype_description=arch.description or "",
                matches_played=played,
                wins=wins,
                draws=draws,
                losses=losses,
                goals_for=round(sum(gf_list) / max(played, 1), 2),
                goals_against=round(sum(ga_list) / max(played, 1), 2),
            )
        )

    return records


# ---------------------------------------------------------------------------
# Main dossier entry point
# ---------------------------------------------------------------------------

async def predict_matchup(
    opponent_id: int,
    fcu_api_football_id: int,
    session: AsyncSession,
) -> MatchupSection:
    """Return the full MatchupSection for the pre-match dossier.

    Steps:
    1. Resolve FCU's internal DB id from api_football_id.
    2. Load archetypes from DB (require build_archetypes.py to have run).
    3. Get opponent's W/D/L record vs each archetype.
    4. Compute FCU's mean feature vector, find nearest centroid (Euclidean
       distance in original feature space; centroids are persisted in the same
       coordinate system).
    5. Build the prediction summary.

    Returns a graceful stub if archetypes are not yet built.
    """
    _stub_summary = (
        "Archetype analysis not yet available. "
        "Run 'uv run python scripts/build_archetypes.py' first."
    )

    # FCU internal id
    fcu_row = (
        await session.execute(
            select(Team).where(Team.api_football_id == fcu_api_football_id)
        )
    ).scalar_one_or_none()
    fcu_internal_id: int | None = fcu_row.id if fcu_row else None

    archetypes = list((await session.execute(select(Archetype))).scalars().all())
    arch_map = {a.id: a for a in archetypes}

    if not archetypes:
        return MatchupSection(
            archetypes=[],
            fcu_archetype_id=0,
            fcu_archetype_name="Unknown",
            prediction_summary=_stub_summary,
            best_archetype_vs_opponent="Unknown",
        )

    opp_records = await get_team_record_vs_archetypes(opponent_id, session)

    fcu_archetype_id = 0
    fcu_archetype_name = "Unknown"

    if fcu_internal_id is not None:
        # Build FCU's team-level feature vector from their match history.
        fcu_matches = list(
            (
                await session.execute(
                    select(Match).where(
                        or_(
                            Match.home_team_id == fcu_internal_id,
                            Match.away_team_id == fcu_internal_id,
                        ),
                        Match.complete(),
                    )
                )
            ).scalars().all()
        )

        per_match_vecs: list[list[float]] = []
        for m in fcu_matches:
            is_home = m.home_team_id == fcu_internal_id
            ts_self = m.stats_home if is_home else m.stats_away
            ts_opp = m.stats_away if is_home else m.stats_home
            gf = int((m.home_score if is_home else m.away_score) or 0)
            ga = int((m.away_score if is_home else m.home_score) or 0)
            v = classify_match(ts_self or {}, ts_opp or {}, gf, ga)
            per_match_vecs.append([v[c] for c in FEATURE_COLS])

        if per_match_vecs:
            fcu_mean = np.array(per_match_vecs).mean(axis=0)
            centers = [a.cluster_center for a in archetypes if a.cluster_center]
            arch_ids = [a.id for a in archetypes if a.cluster_center]
            if centers:
                dists = np.linalg.norm(np.array(centers) - fcu_mean, axis=1)
                nearest = int(np.argmin(dists))
                fcu_archetype_id = arch_ids[nearest]
                fcu_archetype_name = arch_map[fcu_archetype_id].name

    # Best archetype to exploit: opponent's highest loss rate (min 3 matches)
    best_arch_name = "Unknown"
    exploitable = [r for r in opp_records if r.matches_played >= 3]
    if exploitable:
        exploitable.sort(
            key=lambda r: (r.losses / r.matches_played, -r.wins / r.matches_played),
            reverse=True,
        )
        best_arch_name = exploitable[0].archetype_name

    fcu_record = next(
        (r for r in opp_records if r.archetype_id == fcu_archetype_id), None
    )
    if fcu_record and fcu_record.matches_played > 0:
        summary = (
            f"FC U Cluj plays a '{fcu_archetype_name}' style. "
            f"Opponent's record vs this archetype: "
            f"{fcu_record.wins}W {fcu_record.draws}D {fcu_record.losses}L "
            f"({fcu_record.goals_for:.1f} GF / {fcu_record.goals_against:.1f} GA avg). "
            f"Their weakest opponent archetype is '{best_arch_name}'."
        )
    elif fcu_archetype_name != "Unknown":
        summary = (
            f"FC U Cluj plays a '{fcu_archetype_name}' style. "
            f"Insufficient archetype matchup data for this specific opponent. "
            f"Overall, their weakest archetype matchup is '{best_arch_name}'."
        )
    else:
        summary = _stub_summary

    return MatchupSection(
        archetypes=opp_records,
        fcu_archetype_id=fcu_archetype_id,
        fcu_archetype_name=fcu_archetype_name,
        prediction_summary=summary,
        best_archetype_vs_opponent=best_arch_name,
    )
