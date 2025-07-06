import json
import os
from pydantic import DirectoryPath
from typing import List, Dict, Any, Optional
from pydantic_settings import BaseSettings
from src.models.tracked_directory import TrackedDirectory
from src.models.remote import GitRemote
from src.models.version import Version
from src.logger import LoggerFactory
from src.constants import APP_VERSION
from src.common.singleton import Singleton
from src.exceptions import MetadataError


logger = LoggerFactory.getLogger(__name__)


CONFIG_FIELDS = {"version", "directories", "remote"}


class Metadata(BaseSettings, metaclass=Singleton):
    version: Version = APP_VERSION
    directories: List[TrackedDirectory] = []
    remote: Optional[GitRemote] = None
    path: str
    directory_paths: Dict[DirectoryPath, TrackedDirectory] = dict()
    directory_names: Dict[str, TrackedDirectory] = dict()

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
            self.save_to_disk()  # Save new created Metadata

    def model_post_init(self, context: Any, /) -> None:
        self.directory_paths = {dir.path: dir for dir in self.directories}
        self.directory_names = {dir.name: dir for dir in self.directories}

    @staticmethod
    def load_from_disk(path: str) -> Dict[str, Any]:
        with open(path, "r") as file:
            data = json.load(file)
        return data

    def save_to_disk(self) -> None:
        with open(self.path, "w") as file:
            json.dump(self.model_dump(include=CONFIG_FIELDS), file, indent=4)

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
        self.directory_paths[dir.path] = dir
        self.directory_names[dir.name] = dir

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
                self.directory_names.pop(name)
                self.directory_paths.pop(dir.path)
                return
            if path and dir.path == path:
                self.directories.pop(idx)
                self.directory_names.pop(dir.name)
                self.directory_paths.pop(path)
                return

        raise MetadataError(
            "Failed to delete a directory given valid args: ({name}, {path})"
        )

    def get_directory_by_path(self, path: str) -> Optional[TrackedDirectory]:
        return self.directory_paths.get(path, None)

    def get_directory_by_name(self, name: str) -> Optional[TrackedDirectory]:
        return self.directory_names.get(name, None)

    def get_all_directories(self) -> List[TrackedDirectory]:
        return self.directories
