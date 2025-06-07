from pydantic import BaseModel, HttpUrl


class GitRemote(BaseModel):
    url: HttpUrl
    access_token: str