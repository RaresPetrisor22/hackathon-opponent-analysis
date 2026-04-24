from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

RAW_DIR = Path(__file__).parent / "raw" / "wyscout"


class WyscoutLoader:
    """Reads Wyscout per-match JSON exports and upserts player stats to the DB.

    Expected file layout:
        raw/wyscout/{team_name}/{fixture_id}.json   (or any subdirectory structure)

    Each JSON file contains a list of player stat objects with ~115 metrics.
    The loader normalises field names, merges with existing Player rows, and
    writes a flat stats dict to match.stats_home / match.stats_away as needed.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def discover_files(self) -> list[Path]:
        """Return all JSON files under raw/wyscout/."""
        return sorted(RAW_DIR.rglob("*.json"))

    def parse_file(self, path: Path) -> list[dict[str, Any]]:
        """Parse a single Wyscout JSON export and return a list of player stat dicts."""
        # TODO: implement
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else [raw]

    async def upsert_player_stats(self, stats: list[dict[str, Any]]) -> None:
        """Upsert parsed player stats into the Player table."""
        # TODO: implement — match by wyscout_id or name+team, create if missing
        pass

    async def load_all(self) -> int:
        """Discover, parse, and upsert all Wyscout files. Returns count of files processed."""
        # TODO: implement
        files = self.discover_files()
        for f in files:
            stats = self.parse_file(f)
            await self.upsert_player_stats(stats)
        return len(files)
