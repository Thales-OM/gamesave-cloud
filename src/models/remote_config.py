import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CredentialField(BaseModel):
    """
    Declares one configuration option of a storage backend.

    Used by the auth layer to know what to accept as a named CLI arg,
    what to persist to the OS keyring and what to prompt for.
    """

    name: str
    prompt: str  # human label shown when prompting
    secret: bool = (
        False  # secrets are stored in the keyring, never in metadata
    )
    required: bool = True


class RemoteConfig(BaseModel):
    """
    A configured remote storage destination. Non-secret options live in
    `options`; secret options are persisted in the OS keyring under
    gamesave-cloud/remote/<id>/<field>.
    """

    id: str = Field(default_factory=lambda: "remote-" + uuid.uuid4().hex[:8])
    name: str
    type: str  # registry key: filesystem / s3 / webdav / yandex ...
    options: Dict[str, Any] = Field(default_factory=dict)

    def get_option(self, name: str) -> Optional[Any]:
        return self.options.get(name)

    def set_option(self, name: str, value: Any) -> None:
        self.options[name] = value

    def remove_option(self, name: str) -> None:
        self.options.pop(name, None)
