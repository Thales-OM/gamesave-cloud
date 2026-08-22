from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from src.exceptions import EngineNotRegisteredError
from src.models.game import GameEntry
from src.models.snapshot_info import SnapshotInfo

ENGINE_REGISTRY = {}


def register_engine(engine_type: str):
    """Decorator adding a SaveEngine implementation to the registry."""

    def decorator(cls):
        ENGINE_REGISTRY[engine_type] = cls
        cls.ENGINE_TYPE = engine_type
        return cls

    return decorator


def create_engine(game: GameEntry, repos_root: str) -> "SaveEngine":
    """Instantiate the engine configured for a game entry."""
    engine_cls = ENGINE_REGISTRY.get(game.engine_type)
    if not engine_cls:
        raise EngineNotRegisteredError(
            f"Engine type '{game.engine_type}' is not registered. "
            f"Available: {list(ENGINE_REGISTRY)}"
        )
    return engine_cls(game=game, repos_root=repos_root)


class SaveEngine(ABC):
    """
    Versioning backend for one tracked game save folder.

    The engine owns the mapping between a live save folder and its stored
    history (snapshots, branches). Implementations must never store their
    state inside the save folder itself - all internal state goes into
    repos_root.
    """

    def __init__(self, game: GameEntry, repos_root: str):
        self.game = game
        self.repos_root = repos_root

    # ---- lifecycle ----------------------------------------------------

    @abstractmethod
    def init(self) -> None:
        """Prepare storage for this game (idempotent)."""

    # ---- snapshots ------------------------------------------------------

    @abstractmethod
    def has_changes(self) -> bool:
        """True when the live folder differs from the latest snapshot."""

    @abstractmethod
    def snapshot(
        self, message: Optional[str] = None, allow_empty: bool = False
    ) -> Optional[SnapshotInfo]:
        """
        Persist current state of the folder as a new snapshot on the active
        branch. Returns None if nothing changed (and allow_empty is False).
        """

    @abstractmethod
    def list_snapshots(
        self, branch: Optional[str] = None, limit: Optional[int] = None
    ) -> List[SnapshotInfo]:
        """Snapshots on a branch, newest first."""

    @abstractmethod
    def restore(self, snapshot_id: str, hard: bool = False) -> SnapshotInfo:
        """
        Bring the live folder back to the state of a snapshot.

        Default (hard=False) creates a new snapshot restoring the old tree,
        keeping history intact. hard=True moves the branch pointer back.
        """

    # ---- branches -------------------------------------------------------

    @abstractmethod
    def list_branches(self) -> List[str]:
        """All branch names known to the engine."""

    @abstractmethod
    def current_branch(self) -> str:
        """Name of the active branch."""

    @abstractmethod
    def create_branch(
        self, name: str, from_snapshot: Optional[str] = None
    ) -> None:
        """Create a new branch (does NOT switch to it)."""

    @abstractmethod
    def switch_branch(
        self, name: str, auto_snapshot_message: Optional[str] = None
    ) -> None:
        """
        Make another branch active, mutating the live folder to match it.
        Pending changes are snapshotted first so nothing is lost.
        """

    # ---- transport support ----------------------------------------------

    @abstractmethod
    def export_history(self, output_path: str) -> None:
        """Serialize complete history (all branches) into a single artifact."""

    @abstractmethod
    def import_history(self, artifact_path: str) -> None:
        """Merge a previously exported history artifact into local history."""

    @abstractmethod
    def status(self) -> Dict:
        """Engine status summary for CLI/API display."""
