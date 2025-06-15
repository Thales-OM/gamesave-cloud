from pydantic import BaseModel, DirectoryPath
from datetime import datetime


class TrackedDirectory(BaseModel):
    name: str
    path: DirectoryPath
    last_save_time_str: datetime
