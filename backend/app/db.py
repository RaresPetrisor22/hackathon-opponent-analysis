from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    # Import models so their tables are registered with Base.metadata before create_all
    import app.models.match  # noqa: F401
    import app.models.player  # noqa: F401
    import app.models.standings  # noqa: F401
    import app.models.team  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add columns introduced after initial schema creation (SQLite ALTER TABLE)
        for col in ("events", "players_home", "players_away"):
            try:
                await conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE matches ADD COLUMN {col} JSON"
                    )
                )
            except Exception:
                pass  # column already exists
