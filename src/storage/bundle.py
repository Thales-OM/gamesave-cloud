import json
import os
import socket
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple, cast

from src.core.engine.base import SaveEngine
from src.exceptions import StorageError
from src.logger import LoggerFactory
from src.models.game import GameEntry
from src.models.remote_config import RemoteConfig
from src.storage.base import RemoteStorage

logger = LoggerFactory.getLogger(__name__)


class BundleStorage(RemoteStorage):
    """
    Transport for backends that can only store opaque files (object
    storage, WebDAV, plain folders).

    The engine serializes its complete history into a single bundle file;
    subclasses upload/download named artifacts. Layout per game:

        <prefix>/<game.slug>/<timestamp>-<machine>.bundle
        <prefix>/<game.slug>/latest.json   -> {"artifact": ..., ...}
    """

    LATEST_POINTER = "latest.json"

    def __init__(self, config: RemoteConfig, game: GameEntry):
        super().__init__(config=config, game=game)
        self.prefix = self._normalize_prefix(config.options.get("prefix", ""))

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        return "/".join(p for p in prefix.replace("\\", "/").split("/") if p)

    def _base(self) -> str:
        base = f"{self.prefix}/{self.game.slug}" if self.prefix else self.game.slug
        return base

    # ---- artifact naming -------------------------------------------------

    def _artifact_name(self) -> str:
        stamp = time.strftime("%Y%m%dT%H%M%S")
        host = socket.gethostname().replace("/", "_")[:40]
        return f"{stamp}-{host}.bundle"

    # ---- push / pull orchestration -----------------------------------------

    def sync_push(self, engine: SaveEngine) -> str:
        """Export history and upload it; returns the artifact name."""
        base = self._base()
        name = self._artifact_name()
        fd, tmp_bundle = tempfile.mkstemp(suffix=".bundle")
        os.close(fd)
        try:
            engine.export_history(tmp_bundle)
            self.push(tmp_bundle, f"{base}/{name}")
        finally:
            if os.path.exists(tmp_bundle):
                os.remove(tmp_bundle)
        pointer = {
            "artifact": name,
            "pushed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "machine": socket.gethostname(),
            "game": self.game.name,
        }
        self._put_json(f"{base}/{self.LATEST_POINTER}", pointer)
        logger.info(
            f"[{self.game.name}] Pushed history to " f"{self.TYPE}:{base}/{name}"
        )
        return name

    def sync_pull(self, engine: SaveEngine) -> Tuple[str, bool]:
        """Download latest bundle and merge; returns (artifact, changed)."""
        base = self._base()
        pointer = self._get_json(f"{base}/{self.LATEST_POINTER}")
        if not pointer or "artifact" not in pointer:
            raise StorageError(f"No pushed history found at {self.TYPE}:{base}")
        name = cast(str, pointer["artifact"])
        head_before = self._head_commit(engine)
        fd, tmp_bundle = tempfile.mkstemp(suffix=".bundle")
        os.close(fd)
        try:
            self.pull(f"{base}/{name}", tmp_bundle)
            engine.import_history(tmp_bundle)
        finally:
            if os.path.exists(tmp_bundle):
                os.remove(tmp_bundle)
        changed = head_before != self._head_commit(engine)
        logger.info(
            f"[{self.game.name}] Pulled {name} from {self.TYPE} "
            f"({'updated' if changed else 'already up to date'})"
        )
        return name, changed

    def remote_status(self) -> Dict[str, Any]:
        base = self._base()
        status = dict(self.status())
        pointer = self._get_json(f"{base}/{self.LATEST_POINTER}")
        status["latest"] = pointer
        try:
            status["artifacts"] = len(self.list_artifacts(base))
        except Exception:
            status["artifacts"] = None
        return status

    def _head_commit(self, engine: SaveEngine) -> Optional[str]:
        try:
            snaps = engine.list_snapshots(limit=1)
            return snaps[0].id if snaps else "empty"
        except Exception:
            return None

    # ---- primitives to implement---------------------------------------------

    def push(self, artifact_path: str, remote_name: str) -> None:
        raise NotImplementedError

    def pull(self, remote_name: str, local_path: str) -> None:
        raise NotImplementedError

    def list_artifacts(self, prefix: str = "") -> List[str]:
        raise NotImplementedError

    # ---- pointer serialization-----------------------------------------------

    def _put_json(self, remote_name: str, payload: Dict[str, Any]) -> None:
        fd, tmp = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        try:
            self.push(tmp, remote_name)
        finally:
            os.remove(tmp)

    def _get_json(self, remote_name: str) -> Optional[Dict[str, Any]]:
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            try:
                self.pull(remote_name, tmp)
            except Exception:
                return None
            with open(tmp, encoding="utf-8") as f:
                return cast(Dict[str, Any], json.load(f))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
