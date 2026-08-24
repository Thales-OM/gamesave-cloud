from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SnapshotInfo(BaseModel):
    """
    One saved state of a game (a commit in the engine).
    """

    id: str  # engine-specific hash / identifier
    message: str
    timestamp: datetime
    branch: str
    author: Optional[str] = None

    @property
    def short_id(self) -> str:
        return self.id[:8]
