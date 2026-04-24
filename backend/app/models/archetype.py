from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class Archetype(Base):
    __tablename__ = "archetypes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Serialised numpy/list feature vector: [possession, shots_ratio, pass_acc,
    # pressing_proxy, directness, quality]
    cluster_center: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    # List of match IDs assigned to this archetype
    assigned_match_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Archetype {self.name!r}>"
