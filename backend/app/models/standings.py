from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Standing(Base):
    __tablename__ = "standings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    season: Mapped[int] = mapped_column(index=True)
    league_id: Mapped[int] = mapped_column(index=True)

    rank: Mapped[int]
    points: Mapped[int]
    played: Mapped[int]
    wins: Mapped[int]
    draws: Mapped[int]
    losses: Mapped[int]
    goals_for: Mapped[int]
    goals_against: Mapped[int]
    goal_diff: Mapped[int]
    form: Mapped[str | None] = mapped_column(String(10), nullable=True)  # e.g. "WWDLW"
    description: Mapped[str | None] = mapped_column(String(120), nullable=True)
