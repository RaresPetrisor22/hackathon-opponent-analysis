from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.player import Player


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    api_football_id: Mapped[int] = mapped_column(unique=True, index=True)

    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)

    players: Mapped[list[Player]] = relationship("Player", back_populates="team")

    __table_args__ = (Index("ix_teams_name", "name"),)

    def __repr__(self) -> str:
        return f"<Team {self.name!r}>"
