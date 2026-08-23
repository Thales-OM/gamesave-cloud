from watchdog.events import FileSystemEvent, FileSystemEventHandler

from src.core.snapshot_service import SnapshotService
from src.logger import LoggerFactory
from src.models.game import GameEntry

logger = LoggerFactory.getLogger(__name__)


class TrackedDirectoryHandler(FileSystemEventHandler):
    """
    Watchdog handler bound to one tracked game. Every event (file or
    directory) marks the game active in the SnapshotService; debouncing
    and snapshot decisions happen there.
    """

    def __init__(self, game: GameEntry, service: SnapshotService):
        self.game = game
        self.service = service
        super().__init__()

    def on_any_event(self, event: FileSystemEvent) -> None:
        # Ignore events for the vault itself (never watched, but be safe)
        # and transient editor temp files.
        if str(event.src_path).endswith((".tmp", ".swp")):
            return
        try:
            self.service.mark_active(self.game)
        except Exception as ex:
            logger.error(
                f"[{self.game.name}] Error handling FS event "
                f"({event.event_type} {event.src_path!r}): {ex}"
            )
