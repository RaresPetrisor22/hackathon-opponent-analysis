from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.team import Team


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    api_football_id: Mapped[int | None] = mapped_column(nullable=True, index=True)

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    team: Mapped[Team] = relationship("Team", back_populates="players")

    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[str | None] = mapped_column(String(30), nullable=True)
    jersey_number: Mapped[int | None] = mapped_column(nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(60), nullable=True)
    age: Mapped[int | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_players_name", "name"),)

    def __repr__(self) -> str:
        return f"<Player {self.name!r}>"
