from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)  # api_football fixture_id

    season_id: Mapped[int] = mapped_column(index=True)
    league_id: Mapped[int] = mapped_column(index=True)

    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)

    home_score: Mapped[int | None] = mapped_column(nullable=True)
    away_score: Mapped[int | None] = mapped_column(nullable=True)

    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(120), nullable=True)
    referee_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    formation_home: Mapped[str | None] = mapped_column(String(20), nullable=True)
    formation_away: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Raw aggregated stats dicts keyed by API-Football stat label
    stats_home: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stats_away: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Assigned archetype IDs (set by build_archetypes script)
    home_archetype_id: Mapped[int | None] = mapped_column(
        ForeignKey("archetypes.id"), nullable=True
    )
    away_archetype_id: Mapped[int | None] = mapped_column(
        ForeignKey("archetypes.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_matches_teams", "home_team_id", "away_team_id"),
        Index("ix_matches_date", "date"),
    )
