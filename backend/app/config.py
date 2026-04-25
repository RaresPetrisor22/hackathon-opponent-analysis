from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root, one level above backend/
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_football_key: str = ""
    openai_api_key: str = ""
    pinecone_api_key: str = ""
    openai_model: str = "gpt-4o"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    api_football_base_url: str = "https://v3.football.api-sports.io"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Romanian SuperLiga league ID on API-Football
    superliga_league_id: int = 283
    superliga_season: int = 2024

    # FC Universitatea Cluj team ID on API-Football (confirmed from ingest)
    fcu_team_id: int = 2599


settings = Settings()
