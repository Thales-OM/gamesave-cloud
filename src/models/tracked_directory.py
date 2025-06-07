from pydantic import BaseModel
from datetime import datetime


class TrackedDirectory(BaseModel):
    name: str
    path: str
    last_save_time_str: datetime
