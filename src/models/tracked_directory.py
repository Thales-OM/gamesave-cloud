from pydantic import BaseModel, DirectoryPath, field_validator
from typing import Optional
from datetime import datetime
from src.logger import LoggerFactory


logger = LoggerFactory.getLogger(__name__)


class TrackedDirectory(BaseModel):
    name: str
    path: DirectoryPath
    last_save_time: Optional[datetime] = None

    @field_validator("last_save_time_str", mode="after")
    def verify_timezone(self, value: datetime) -> Optional[datetime]:
        if value.tzinfo is None:
            logger.warning(
                "Got a last_save_time without a timezone, \
                    setting value to None"
            )
            return None
        return value
