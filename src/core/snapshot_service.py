import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from src.core.engine.base import SaveEngine, create_engine
from src.exceptions import EngineError
from src.logger import LoggerFactory
from src.models.game import GameEntry
from src.models.snapshot_info import SnapshotInfo

logger = LoggerFactory.getLogger(__name__)


class _GameState:
    """Per-game debounce state (owned by SnapshotService)."""

    def __init__(self):
        self.timer: Optional[threading.Timer] = None
        self.last_event: float = 0.0
        self.last_snapshot: float = 0.0


class SnapshotService:
    """
    Turns filesystem activity into debounced automatic snapshots.

    Strategy per game:
      - every write event resets a quiet-period timer;
      - when the folder stays quiet for `quiet_period_sec`, a snapshot is
        taken if at least `cooldown_sec` passed since the previous one.
    Manual snapshots bypass both timers via snapshot_now().
    """

    def __init__(
        self,
        repos_root: str,
        quiet_period_sec: int = 30,
        cooldown_sec: int = 300,
        limit_intervals: bool = True,
        game_resolver: Optional[Callable[[str], Optional[GameEntry]]] = None,
        on_snapshotted: Optional[
            Callable[[GameEntry, SnapshotInfo], None]
        ] = None,
    ):
        self.repos_root = repos_root
        self.quiet_period_sec = max(1, int(quiet_period_sec))
        self.cooldown_sec = max(0, int(cooldown_sec))
        self.limit_intervals = limit_intervals
        self._resolver = game_resolver
        self._on_snapshotted = on_snapshotted
        self._lock = threading.RLock()
        self._states: Dict[str, _GameState] = {}
        self._engines: Dict[str, SaveEngine] = {}

    # ---- engines -------------------------------------------------------

    def engine_for(self, game: GameEntry) -> SaveEngine:
        with self._lock:
            engine = self._engines.get(game.id)
            if engine is None:
                engine = create_engine(game=game, repos_root=self.repos_root)
                self._engines[game.id] = engine
            return engine

    def drop_engine(self, game_id: str) -> None:
        with self._lock:
            self._engines.pop(game_id, None)

    # ---- activity tracking ---------------------------------------------

    def mark_active(self, game: GameEntry) -> None:
        """Called on any filesystem event inside the game's save folder."""
        with self._lock:
            state = self._states.setdefault(game.id, _GameState())
            state.last_event = time.monotonic()
            if game.auto_snapshot is False:
                return
            if state.timer is not None:
                state.timer.cancel()
            state.timer = threading.Timer(
                self.quiet_period_sec,
                self._quiet_elapsed,
                args=(game.id,),
            )
            state.timer.daemon = True
            state.timer.start()
            logger.debug(
                f"[{game.name}] Activity detected; debounce timer "
                f"reset ({self.quiet_period_sec}s)"
            )

    def stop_tracking(self, game_id: str) -> None:
        with self._lock:
            state = self._states.pop(game_id, None)
            if state and state.timer is not None:
                state.timer.cancel()
            self.drop_engine(game_id)

    def _quiet_elapsed(self, game_id: str) -> None:
        try:
            game: Optional[GameEntry] = None
            if self._resolver is not None:
                game = self._resolver(game_id)
            if game is None or not game.auto_snapshot:
                return
            self.maybe_snapshot(game)
        except Exception as ex:
            logger.error(f"Auto-snapshot failed for {game_id}: {ex}")

    def maybe_snapshot(self, game: GameEntry) -> Optional[SnapshotInfo]:
        """Snapshot only when changes exist AND the cooldown allows it."""
        if self.limit_intervals:
            with self._lock:
                state = self._states.setdefault(game.id, _GameState())
                elapsed = time.monotonic() - state.last_snapshot
                if elapsed < self.cooldown_sec:
                    logger.debug(
                        f"[{game.name}] Cooldown active "
                        f"({self.cooldown_sec - elapsed:.0f}s left)"
                    )
                    return None
        return self.snapshot_now(game, message=None)

    def snapshot_now(
        self,
        game: GameEntry,
        message: Optional[str] = None,
        allow_empty: bool = False,
    ) -> Optional[SnapshotInfo]:
        """Manual-path snapshot: ignores debounce + cooldown."""
        engine = self.engine_for(game)
        info = engine.snapshot(message=message, allow_empty=allow_empty)
        with self._lock:
            state = self._states.setdefault(game.id, _GameState())
            state.last_snapshot = time.monotonic()
        if info:
            logger.info(
                f"[{game.name}] Snapshotted {info.short_id}: {info.message}"
            )
            if self._on_snapshotted is not None:
                try:
                    self._on_snapshotted(game, info)
                except Exception as ex:
                    logger.error(
                        f"[{game.name}] post-snapshot hook failed: {ex}"
                    )
        return info

    def notify_external_snapshot(self, game_id: str) -> None:
        """Let the service know a snapshot happened outside its control."""
        with self._lock:
            state = self._states.setdefault(game_id, _GameState())
            state.last_snapshot = time.monotonic()

    def status_line(self, game: GameEntry) -> dict:
        with self._lock:
            state = self._states.get(game.id)
            last_event = (
                datetime.now(timezone.utc)
                if state is None or state.last_event == 0
                else None
            )
            pending = bool(state and state.timer is not None)
            return {
                "auto_watch": game.auto_snapshot,
                "debounce_pending": pending,
                "quiet_period_sec": self.quiet_period_sec,
                "cooldown_sec": self.cooldown_sec,
                "last_event": str(last_event),
            }


def snapshot_safely(service: SnapshotService, game: GameEntry, message):
    """Helper used by API layer so engine errors never kill handlers."""
    try:
        return service.snapshot_now(game, message=message)
    except EngineError as ex:
        logger.error(f"[{game.name}] Snapshot error: {ex}")
        raise
