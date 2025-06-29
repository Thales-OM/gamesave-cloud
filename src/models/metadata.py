import json
import os
from pydantic import FilePath, DirectoryPath
from typing import List, Dict, Any, Set, Optional
from pydantic_settings import BaseSettings
from src.models.tracked_directory import TrackedDirectory
from src.models.remote import GitRemote
from src.models.version import Version
from src.logger import LoggerFactory
from src.constraints import APP_VERSION
from src.exceptions import MetadataError


logger = LoggerFactory.getLogger(__name__)


CONFIG_FIELDS = {"version", "directories", "remotes"}


class Metadata(BaseSettings):
    version: Version = APP_VERSION
    directories: List[TrackedDirectory] = []
    remotes: List[GitRemote] = []
    path: FilePath
    directory_paths: Set[DirectoryPath] = set()
    directory_names: Set[str] = set()

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(Metadata, cls).__new__(cls)
        return cls._instance

    def __init__(self, path: str):
        path = os.path.abspath(path)

        data = None
        try:
            data = Metadata.load_from_disk(path=path)
        except FileNotFoundError:
            logger.warning(
                "Failed to load metadata from disk. \
                    File not found. Initializing empty metadata."
            )
        except Exception as ex:
            logger.warning(
                f"Failed to load metadata from disk for unknown reason. \
                    Initializing empty metadata. Detail: \n{ex}"
            )

        if data:
            super().__init__(path=path, **data)
        else:
            super().__init__(path=path)

    def model_post_init(self, context: Any, /) -> None:
        self.directory_paths = set([dir.path for dir in self.directories])
        self.directory_names = set([dir.name for dir in self.directories])

    @staticmethod
    def load_from_disk(path: str) -> Dict[str, Any]:
        with open(path, "r") as file:
            data = json.load(file)
        return data

    def save_to_disk(self) -> None:
        with open(self.path, "w") as file:
            json.dump(self.model_dump_json(include=CONFIG_FIELDS), file)

    def add_directory(self, dir: TrackedDirectory) -> None:
        if dir.path in self.directory_paths:
            raise MetadataError(
                f"Attempted to add an already present \
                           directory to Metadata: {dir.path}. Skipping."
            )
        if dir.name in self.directory_names:
            raise MetadataError(
                f"Attempted to add a directory with a duplicate \
                           name to Metadata: {dir.name}. Skipping."
            )

        self.directories.append(dir)
        self.directory_paths.add(dir.path)
        self.directory_names.add(dir.name)

    def delete_directory(
        self, name: Optional[str], path: Optional[DirectoryPath]
    ) -> None:
        if not (name or path):
            raise MetadataError(
                "Neither name nor path were \
                                provided to Metadata.delete_directory"
            )
        if name and path:
            logger.warning(
                f"Passed both name and path to \
                    Metadata.delete_directory: ({name}, {path}).\
                        Prioritizing name."
            )

        if name and name not in self.directory_names:
            raise MetadataError("Tried to delete name not present in Metadata")
        if not name and path not in self.directory_paths:
            raise MetadataError("Tried to delete path not present in Metadata")

        for idx, dir in enumerate(self.directories):
            if name and dir.name == name:
                self.directories.pop(idx)
                self.directory_names.remove(name)
                self.directory_paths.remove(dir.path)
                return
            if path and dir.path == path:
                self.directories.pop(idx)
                self.directory_names.remove(dir.name)
                self.directory_paths.remove(path)
                return

        raise MetadataError(
            "Failed to delete a directory given valid args: ({name}, {path})"
        )
