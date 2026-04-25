from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RefereeProfile(Base):
    __tablename__ = "referee_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    total_matches: Mapped[int]

    avg_yellow_cards: Mapped[float]
    avg_red_cards: Mapped[float]
    avg_fouls: Mapped[float]

    # % of matches where the home team won (in this referee's matches)
    home_win_pct: Mapped[float]
    # ratio vs league-wide home win % — >1.0 means referee favours home side
    home_advantage_factor: Mapped[float]
