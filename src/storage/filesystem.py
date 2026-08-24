import glob
import os
import shutil
from typing import List

from src.exceptions import StorageError
from src.models.game import GameEntry
from src.models.remote_config import CredentialField, RemoteConfig
from src.storage.base import register_storage
from src.storage.bundle import BundleStorage


@register_storage("filesystem")
class FilesystemStorage(BundleStorage):
    """
    Stores history bundles in a plain folder: a USB drive, a network
    share, or any mounted location.

    Options:
      path   (required) destination directory
      prefix (optional) subdirectory inside it
    """

    FIELDS = (
        CredentialField(
            name="path",
            prompt="Destination folder path",
            secret=False,
            required=True,
        ),
        CredentialField(
            name="prefix",
            prompt="Subfolder inside destination (optional)",
            secret=False,
            required=False,
        ),
    )

    def __init__(self, config: RemoteConfig, game: GameEntry):
        super().__init__(config=config, game=game)
        self.root = os.path.abspath(str(self.option("path", "")))
        if not self.root:
            raise StorageError("filesystem storage requires 'path' option")

    def _abs(self, remote_name: str) -> str:
        return os.path.join(self.root, *remote_name.split("/"))

    def test_connection(self) -> None:
        try:
            os.makedirs(self.root, exist_ok=True)
            probe = os.path.join(self.root, ".gsc-write-test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
        except OSError as ex:
            raise StorageError(f"Cannot write to {self.root}: {ex}") from ex

    def push(self, artifact_path: str, remote_name: str) -> None:
        target = self._abs(remote_name)
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            tmp_target = target + ".tmp"
            shutil.copyfile(artifact_path, tmp_target)
            os.replace(tmp_target, target)
        except OSError as ex:
            raise StorageError(f"Upload failed: {ex}") from ex

    def pull(self, remote_name: str, local_path: str) -> None:
        source = self._abs(remote_name)
        if not os.path.exists(source):
            raise StorageError(f"Not found on remote: {remote_name}")
        try:
            shutil.copyfile(source, local_path)
        except OSError as ex:
            raise StorageError(f"Download failed: {ex}") from ex

    def list_artifacts(self, prefix: str = "") -> List[str]:
        base = self._abs(prefix) if prefix else self._base()
        pattern = os.path.join(base, "*.bundle")
        root = os.path.abspath(self.root)
        return sorted(
            os.path.relpath(p, root).replace("\\", "/") for p in glob.glob(pattern)
        )
