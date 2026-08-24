import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from pydantic import BaseModel, DirectoryPath, Field, field_validator
from src.constants import DEFAULT_MASTER_BRANCH


class PlatformHint(BaseModel):
    """
    Records where a game entry came from (steam appid, epic manifest, etc.)
    """

    provider: str = "manual"
    platform_game_id: Optional[str] = None  # e.g. steam appid "1245620"
    executable_path: Optional[str] = None


class GameEntry(BaseModel):
    """
    A single tracked game save folder. One git repo in the vault per entry.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    path: DirectoryPath
    engine_type: str = "git"
    auto_snapshot: bool = True
    default_branch: str = DEFAULT_MASTER_BRANCH
    remote_id: Optional[str] = None  # RemoteConfig this game pushes to
    auto_push: bool = False  # push to remote after every snapshot
    platform_hint: Optional[PlatformHint] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("path", mode="after")
    @classmethod
    def make_path_absolute(cls, value: Path) -> Path:
        return Path(os.path.abspath(value))

    @field_validator("default_branch")
    @classmethod
    def validate_branch_name(cls, value: str) -> str:
        if not re.fullmatch(r"[\w.\-/]+", value):
            raise ValueError(f"Invalid branch name: {value}")
        return value

    @property
    def slug(self) -> str:
        """
        Stable filesystem-safe identifier derived from the name alone -
        MUST be identical across machines so they converge on the same
        remote path. Local uniqueness is enforced by add_game().
        """
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", self.name).strip("._-")
        return (slug or "game").lower()

    @staticmethod
    def create_name_auto(path: str) -> str:
        return os.path.basename(os.path.normpath(path))
