import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from src.constants import APP_VERSION, METADATA_SCHEMA_VERSION
from src.exceptions import MetadataError, MetadataMigrationError
from src.logger import LoggerFactory
from src.models.game import GameEntry
from src.models.remote_config import RemoteConfig

logger = LoggerFactory.getLogger(__name__)

CONFIG_FIELDS = {"version", "games", "remotes"}


class Metadata(BaseModel):
    """
    Central state of the application: tracked games and configured remotes.

    Schema version 0.2.0. Migrates transparently from the 0.1.x layout
    (directories + git remote).
    """

    version: str = METADATA_SCHEMA_VERSION
    games: List[GameEntry] = Field(default_factory=list)
    remotes: List[RemoteConfig] = Field(default_factory=list)

    # Runtime-only, not persisted
    path: str = ""

    @classmethod
    def load(cls, path: str) -> "Metadata":
        """Load metadata from disk; migrate legacy schemas if needed."""
        path = os.path.abspath(path)
        data: Optional[Dict[str, Any]] = None
        if os.path.exists(path):
            try:
                with open(path, "r") as file:
                    data = json.load(file)
            except Exception as ex:
                logger.warning(
                    f"Failed to read metadata at {path}, starting fresh: {ex}"
                )
                data = None

        migrated = False
        if data and "directories" in data:
            try:
                data = cls._migrate_v1(data)
                migrated = True
            except Exception as ex:
                raise MetadataMigrationError(
                    f"Failed to migrate metadata schema at {path}: {ex}"
                ) from ex

        meta = cls(path=path, **(data or {}))
        if migrated:
            logger.info("Metadata migrated from 0.1.x to %s", APP_VERSION)
        meta.save()
        return meta

    @staticmethod
    def _migrate_v1(data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert the 0.1.x {directories, remote} layout to v2."""
        logger.info("Migrating metadata from schema 0.1.x")
        games = []
        for directory in data.get("directories", []):
            entry = {
                "name": directory.get("name"),
                "path": directory.get("path"),
                "auto_snapshot": True,
            }
            games.append({k: v for k, v in entry.items() if v is not None})

        if data.get("remote"):
            logger.warning(
                "Legacy git remote found in metadata. Git-hosting remotes are "
                "no longer auto-migrated - re-add it via `gsc remote add`."
            )

        return {
            "version": METADATA_SCHEMA_VERSION,
            "games": games,
            "remotes": [],
        }

    def save(self) -> None:
        """Atomically persist metadata (write tmp file, then replace)."""
        if not self.path:
            raise MetadataError("Metadata path is not set")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = self.model_dump(include=CONFIG_FIELDS, exclude_none=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(self.path), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as file:
                json.dump(payload, file, indent=4, default=str)
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    # ---- game lookups -------------------------------------------------

    def add_game(self, game: GameEntry) -> None:
        for existing in self.games:
            if existing.id == game.id:
                raise MetadataError(f"Game with id already present: {game.id}")
            if existing.path == game.path:
                raise MetadataError(f"Path already tracked: {game.path}")
            if existing.name.lower() == game.name.lower():
                raise MetadataError(f"Name already in use: {game.name}")
        self.games.append(game)

    def remove_game(self, name_or_id: str) -> GameEntry:
        game = self.find_game(name_or_id)
        if not game:
            raise MetadataError(f"Game not found: {name_or_id}")
        self.games.remove(game)
        return game

    def find_game(self, name_or_id: str) -> Optional[GameEntry]:
        needle = name_or_id.strip().lower()
        for game in self.games:
            if game.id == name_or_id or game.slug == name_or_id:
                return game
        for game in self.games:
            if game.name.lower() == needle:
                return game
        for game in self.games:
            # Partial match as a convenience (unique prefix wins).
            if needle in game.name.lower():
                return game
        return None

    def find_game_by_path(self, path: str) -> Optional[GameEntry]:
        abspath = os.path.abspath(path)
        for game in self.games:
            if game.path == abspath:
                return game
        return None

    # ---- remote lookups -----------------------------------------------

    def add_remote(self, remote: RemoteConfig) -> None:
        for existing in self.remotes:
            if existing.id == remote.id:
                raise MetadataError(f"Remote id already present: {remote.id}")
            if existing.name.lower() == remote.name.lower():
                raise MetadataError(
                    f"Remote name already in use: {remote.name}"
                )
        self.remotes.append(remote)

    def remove_remote(self, name_or_id: str) -> RemoteConfig:
        remote = self.find_remote(name_or_id)
        if not remote:
            raise MetadataError(f"Remote not found: {name_or_id}")
        self.remotes.remove(remote)
        return remote

    def find_remote(self, name_or_id: str) -> Optional[RemoteConfig]:
        for remote in self.remotes:
            if remote.id == name_or_id:
                return remote
        for remote in self.remotes:
            if remote.name.lower() == name_or_id.strip().lower():
                return remote
        return None

    def remote_for_game(self, game: GameEntry) -> Optional[RemoteConfig]:
        if not game.remote_id:
            return None
        return self.find_remote(game.remote_id)
