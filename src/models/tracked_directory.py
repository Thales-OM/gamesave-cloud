import os
from pydantic import BaseModel, DirectoryPath, field_validator
from typing import Optional
from datetime import datetime
from pathlib import Path
from src.logger import LoggerFactory


logger = LoggerFactory.getLogger(__name__)


class TrackedDirectory(BaseModel):
    name: str
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
    def make_path_absolute(cls, value) -> DirectoryPath:
        return Path(os.path.abspath(value))
