import os
from pydantic import BaseModel, DirectoryPath, field_validator
from typing import Optional
from datetime import datetime
from pathlib import Path
from src.logger import LoggerFactory


logger = LoggerFactory.getLogger(__name__)


class TrackedDirectory(BaseModel):
    name: Optional[str]
    path: DirectoryPath
    last_save_time: Optional[datetime] = None

    @field_validator("last_save_time", mode="after")
    @classmethod
    def verify_timezone(cls, value: datetime) -> Optional[datetime]:
        if value.tzinfo is None:
            logger.warning(
                "Got a last_save_time without a timezone, \
                    setting value to None"
            )
            return None
        return value

    @field_validator("path", mode="after")
    @classmethod
    def make_path_absolute(cls, value: DirectoryPath) -> DirectoryPath:
        return Path(os.path.abspath(value))

    @staticmethod
    def create_name_auto(path: str) -> str:
        return os.path.basename(path)

    @field_validator("name", mode="after")
    def make_path_absolute(self, value: Optional[str]) -> str:
        if value:
            return value
        synth_name = TrackedDirectory.create_name_auto(path=self.path)
        logger.info(f"No name was provided for directory at path: {self.path}. Automatically assigning: {synth_name}.")
        return synth_name
