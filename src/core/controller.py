from typing import Dict, List, Optional

from pydantic import DirectoryPath
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from src.core.event_handler import TrackedDirectoryHandler
from src.core.snapshot_service import SnapshotService
from src.exceptions import (
    ControllerCallError,
    GameNotFoundError,
)
from src.logger import LoggerFactory
from src.models.game import GameEntry
from src.models.metadata import Metadata

logger = LoggerFactory.getLogger(__name__)


class DirectoryController:
    """
    Owns the watchdog observers (one per tracked game) and routes their
    events into the SnapshotService. Persists game entries via Metadata.
    """

    def __init__(
        self,
        metadata: Metadata,
        snapshot_service: SnapshotService,
    ):
        self.metadata = metadata
        self.service = snapshot_service
        self.observers: Dict[str, BaseObserver] = {}
        self.status: str = "initialized"

    # ---- games -----------------------------------------------------------

    @property
    def games(self) -> List[GameEntry]:
        return self.metadata.games

    def get_game(self, name_or_id: str) -> GameEntry:
        game = self.metadata.find_game(name_or_id)
        if not game:
            raise GameNotFoundError(f"Game not found: {name_or_id}")
        return game

    def add_game(
        self,
        path: DirectoryPath,
        name: Optional[str] = None,
        auto_snapshot: bool = True,
    ) -> GameEntry:
        from src.models.game import GameEntry

        game = GameEntry(
            name=name or GameEntry.create_name_auto(path),
            path=path,
            auto_snapshot=auto_snapshot,
        )
        self.metadata.add_game(game)
        self.metadata.save()
        if game.auto_snapshot and self.status == "started":
            self.start_observer(game)
        logger.info(f"Added game '{game.name}' at {game.path}")
        return game

    def remove_game(self, name_or_id: str) -> GameEntry:
        game = self.get_game(name_or_id)
        self.stop_observer(game.id)
        self.service.stop_tracking(game.id)
        removed = self.metadata.remove_game(name_or_id)
        self.metadata.save()
        logger.info(f"Removed game '{removed.name}'")
        return removed

    # ---- observers ----------------------------------------------------------

    def start_observer(self, game: GameEntry) -> None:
        if game.id in self.observers:
            logger.warning(f"Observer already running for '{game.name}'")
            return
        observer = Observer()
        handler = TrackedDirectoryHandler(game=game, service=self.service)
        observer.schedule(handler, game.path, recursive=True)
        observer.daemon = True
        observer.start()
        self.observers[game.id] = observer
        logger.info(f"Watching save folder: {game.path}")

    def stop_observer(self, game_id: str) -> None:
        observer = self.observers.pop(game_id, None)
        if observer:
            observer.unschedule_all()
            observer.stop()
            observer.join(timeout=5)

    # ---- lifecycle -------------------------------------------------------

    def start_all(self) -> None:
        if self.status == "started":
            raise ControllerCallError("Controller already started")
        self.status = "starting"
        for game in list(self.games):
            if game.auto_snapshot:
                try:
                    self.start_observer(game)
                except Exception as ex:
                    logger.error(f"Failed to watch {game.path}: {ex}")
        self.status = "started"
        logger.info(
            f"Controller started with {len(self.observers)} watcher(s)"
        )

    def stop_all(self) -> None:
        if self.status == "stopped":
            raise ControllerCallError("Controller already stopped")
        self.status = "stopping"
        for game_id in list(self.observers):
            self.stop_observer(game_id)
        for game in list(self.games):
            self.service.stop_tracking(game.id)
        self.status = "stopped"
        logger.info("All directory watchers stopped")
