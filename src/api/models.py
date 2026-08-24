from typing import Any, Dict, Optional

from pydantic import BaseModel, DirectoryPath


class CreateGameRequest(BaseModel):
    path: DirectoryPath
    name: Optional[str] = None
    auto_snapshot: bool = True


class SnapshotRequest(BaseModel):
    message: Optional[str] = None
    allow_empty: bool = False


class RestoreRequest(BaseModel):
    snapshot_id: str
    hard: bool = False


class CreateBranchRequest(BaseModel):
    name: str
    from_snapshot: Optional[str] = None
    switch: bool = False


class SwitchBranchRequest(BaseModel):
    branch: str


class CreateRemoteRequest(BaseModel):
    type: str
    name: str
    options: Dict[str, Any] = {}


class AssignRemoteRequest(BaseModel):
    remote_id: Optional[str] = None  # null clears assignment


class TestRemoteRequest(BaseModel):
    type: str = ""
    options: Dict[str, Any] = {}
    id: Optional[str] = None  # test an existing configured remote


class PushRequest(BaseModel):
    game: Optional[str] = None  # name/id; None = all games with a remote
    remote: Optional[str] = None  # override game's default remote


class PullRequest(PushRequest):
    pass


class DetectRequest(BaseModel):
    executable_path: Optional[str] = None
    query: Optional[str] = None  # free-text game title lookup
