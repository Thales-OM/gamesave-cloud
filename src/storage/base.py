from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

from src.exceptions import StorageNotRegisteredError
from src.models.game import GameEntry
from src.models.remote_config import CredentialField, RemoteConfig

STORAGE_REGISTRY: Dict[str, type] = {}


def register_storage(storage_type: str):
    """Decorator adding a RemoteStorage implementation to the registry."""

    def decorator(cls):
        STORAGE_REGISTRY[storage_type] = cls
        cls.TYPE = storage_type
        return cls

    return decorator


def get_storage_class(storage_type: str):
    cls = STORAGE_REGISTRY.get(storage_type)
    if not cls:
        raise StorageNotRegisteredError(
            f"Storage type '{storage_type}' is not registered. "
            f"Available: {sorted(STORAGE_REGISTRY)}"
        )
    return cls


def create_storage(config: RemoteConfig, game: GameEntry) -> "RemoteStorage":
    return get_storage_class(config.type)(config=config, game=game)


class PushResult:
    def __init__(self, artifact: str, snapshots: int):
        self.artifact = artifact
        self.snapshots = snapshots


class RemoteStorage(ABC):
    """
    A destination for a game's complete history.

    Implementations transport engine-produced artifacts; they never touch
    the save folder or the vault themselves. Custom backends subclass this
    class and register with @register_storage("mytype").
    """

    TYPE: str = ""
    # Declares CLI/API options: which are secrets (keyring), prompts, etc.
    FIELDS: Tuple[CredentialField, ...] = ()

    def __init__(self, config: RemoteConfig, game: GameEntry):
        self.config = config
        self.game = game

    # ---- configuration helpers -----------------------------------------

    def option(self, name: str, default=None):
        return self.config.options.get(name, default)

    def secret(self, name: str) -> str:
        from src.auth.credentials import load_secret

        value = load_secret(self.config.id, name)
        if not value:
            from src.exceptions import StorageAuthError

            raise StorageAuthError(
                f"Credential '{name}' for remote '{self.config.name}' "
                f"is not configured. Re-run: gsc remote add"
            )
        return value

    @classmethod
    def fields(cls) -> List[CredentialField]:
        return list(cls.FIELDS)

    # ---- contract ----------------------------------------------------------

    @abstractmethod
    def test_connection(self) -> None:
        """Raise StorageError when the destination cannot be reached."""

    @abstractmethod
    def push(self, artifact_path: str, remote_name: str) -> None:
        """Upload one history artifact produced by the engine."""

    @abstractmethod
    def pull(self, remote_name: str, local_path: str) -> None:
        """Download a named history artifact to local_path."""

    @abstractmethod
    def list_artifacts(self, prefix: str = "") -> List[str]:
        """Names of stored artifacts for this game."""

    def status(self) -> dict:
        try:
            self.test_connection()
            reachable = True
            error = None
        except Exception as ex:
            reachable = False
            error = str(ex)
        return {"type": self.TYPE, "reachable": reachable, "error": error}
