import threading
from typing import Optional

from src.core.controller import DirectoryController
from src.core.snapshot_service import SnapshotService
from src.models.metadata import Metadata

_lock = threading.Lock()
_state: Optional["AppState"] = None


class AppState:
    """Process-wide singletons shared by all API routes."""

    def __init__(
        self,
        metadata: Metadata,
        controller: DirectoryController,
        service: SnapshotService,
    ):
        self.metadata = metadata
        self.controller = controller
        self.service = service


def set_state(state: AppState) -> None:
    global _state
    with _lock:
        _state = state


def get_state() -> AppState:
    assert _state is not None, "AppState not initialized"
    return _state
