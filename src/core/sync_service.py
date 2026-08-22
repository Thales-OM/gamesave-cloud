import threading
from typing import Dict, List, Optional

from src.exceptions import MetadataError
from src.logger import LoggerFactory
from src.models.game import GameEntry
from src.models.metadata import Metadata
from src.models.remote_config import RemoteConfig
from src.storage import create_storage
from src.storage.base import RemoteStorage

logger = LoggerFactory.getLogger(__name__)

_push_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class SyncService:
    """
    Orchestrates pushing/pulling game history through remote storages.
    Pushes of the same game are serialized to avoid interleaved uploads.
    """

    def __init__(self, metadata: Metadata, engine_resolver):
        self.metadata = metadata
        self.engine_resolver = engine_resolver  # game -> SaveEngine

    # ---- resolution ------------------------------------------------------

    def _remote_for(
        self, game: GameEntry, override: Optional[str] = None
    ) -> RemoteConfig:
        remote = (
            self.metadata.find_remote(override)
            if override
            else self.metadata.remote_for_game(game)
        )
        if not remote:
            hint = f"'{override}'" if override else "for this game"
            raise MetadataError(
                f"No remote configured {hint}. " f"Add one: gsc remote add"
            )
        return remote

    def _storage_and_engine(
        self, game: GameEntry, override_remote: Optional[str] = None
    ) -> tuple:
        remote = self._remote_for(game, override_remote)
        storage = create_storage(config=remote, game=game)
        engine = self.engine_resolver(game)
        return storage, engine

    def _lock_for(self, game_id: str) -> threading.Lock:
        with _locks_guard:
            if game_id not in _push_locks:
                _push_locks[game_id] = threading.Lock()
            return _push_locks[game_id]

    # ---- operations ---------------------------------------------------------

    def push_game(
        self, game: GameEntry, override_remote: Optional[str] = None
    ) -> str:
        """Snapshot-then-push; returns artifact name."""
        storage, engine = self._storage_and_engine(game, override_remote)
        with self._lock_for(game.id):
            # Make sure pending changes travel with the push.
            engine.snapshot(message="auto: snapshot before push")
            artifact = storage.sync_push(engine)
        logger.info(f"[{game.name}] Push complete ({artifact})")
        return artifact

    def pull_game(
        self, game: GameEntry, override_remote: Optional[str] = None
    ) -> bool:
        """Returns True when local history changed."""
        storage, engine = self._storage_and_engine(game, override_remote)
        with self._lock_for(game.id):
            _, changed = storage.sync_pull(engine)
        return changed

    def test_remote(self, name_or_id: str) -> dict:
        remote = self.metadata.find_remote(name_or_id)
        if not remote:
            raise MetadataError(f"Remote not found: {name_or_id}")
        dummy = (
            self.metadata.games[0]
            if self.metadata.games
            else GameEntry(name="_probe", path=".")
        )
        storage = create_storage(config=remote, game=dummy)
        result = {"name": remote.name, "type": remote.type}
        try:
            storage.test_connection()
            result["reachable"] = True
        except Exception as ex:
            result["reachable"] = False
            result["error"] = str(ex)
        return result

    def status_for_game(self, game: GameEntry) -> Optional[dict]:
        remote = self.metadata.remote_for_game(game)
        if not remote:
            return None
        storage: RemoteStorage = create_storage(config=remote, game=game)
        try:
            detail = storage.remote_status()
        except Exception as ex:
            detail = {"error": str(ex)}
        return {"remote": remote.name, "type": remote.type, **detail}

    def push_async(self, game: GameEntry) -> None:
        """Fire-and-forget background push used after auto-snapshots."""

        def worker():
            try:
                self.push_game(game)
            except Exception as ex:
                logger.error(f"[{game.name}] Background push failed: {ex}")

        threading.Thread(target=worker, daemon=True).start()

    def games_with_remotes(self) -> List[GameEntry]:
        return [g for g in self.metadata.games if g.remote_id]
