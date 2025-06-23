import json
import os
from pydantic import FilePath
from typing import List, Dict, Any
from pydantic_settings import BaseSettings
from src.models.tracked_directory import TrackedDirectory
from src.models.remote import GitRemote
from src.models.version import Version
from src.logger import LoggerFactory
from src.constraints import APP_VERSION


logger = LoggerFactory.getLogger(__name__)


class Metadata(BaseSettings):
    version: Version = APP_VERSION
    directories: List[TrackedDirectory] = []
    remotes: List[GitRemote] = []
    path: FilePath

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

    @staticmethod
    def load_from_disk(path: str) -> Dict[str, Any]:
        with open(path, "r") as file:
            data = json.load(file)
        return data

    def save_to_disk(self) -> None:
        with open(self.path, "w") as file:
            json.dump(self.model_dump_json, file)
