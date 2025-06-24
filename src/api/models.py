from pydantic import BaseModel, DirectoryPath


class CreateDirectoryRequest(BaseModel):
    name: str
    path: DirectoryPath
