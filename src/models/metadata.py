import json
from typing import List, Dict, Any
from pydantic_settings import BaseSettings
from src.models.tracked_directory import TrackedDirectory
from src.models.remote import GitRemote
from src.models.version import Version
from src.settings import settings
from src.logger import LoggerFactory
from src.constraints import APP_VERSION


logger = LoggerFactory.getLogger(__name__)


class Metadata(BaseSettings):
    version: Version = APP_VERSION
    directories: List[TrackedDirectory] = []
    remotes: List[GitRemote] = []

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(Metadata, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        data = None
        try:
            data = Metadata.load_from_disk()
        except FileNotFoundError:
            logger.warning(
                "Failed to load metdata from disk. \
                    File not found. Initializing empty metadata."
            )
        except Exception as ex:
            logger.warning(
                f"Failed to load metdata from disk for unknown reason. \
                    Initializing empty metadata. Detail: \n{ex}"
            )

        if data:
            super().__init__(**data)
        else:
            super().__init__()

    @staticmethod
    def load_from_disk() -> Dict[str, Any]:
        with open(settings.metadata.storage_filepath, "r") as file:
            data = json.load(file)
        return data

    def save_to_disk(self) -> None:
        with open(settings.metadata.storage_filepath, "w") as file:
            json.dump(self.model_dump_json, file)
