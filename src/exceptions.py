class AvailablePortNotFoundError(Exception):
    """
    No available port was found to host the daemon process server
    """


class ControllerCallError(Exception):
    """
    An invalid request was made to the Controller
    """


class MetadataError(Exception):
    """
    Base class for errors during Metadata initialization/operations
    """


class MetadataMigrationError(MetadataError):
    """
    Failed to migrate an old metadata schema to the current one
    """


class EngineError(Exception):
    """
    Base class for errors raised by save engines
    """


class EngineNotRegisteredError(EngineError):
    """
    Requested engine type is not registered
    """


class GitEngineError(EngineError):
    """
    Error while performing a git operation
    """


class SnapshotNotFoundError(EngineError):
    """
    Requested snapshot does not exist
    """


class BranchError(EngineError):
    """
    Invalid branch operation (missing branch, duplicate, etc.)
    """


class StorageError(Exception):
    """
    Base class for remote storage backend errors
    """


class StorageNotRegisteredError(StorageError):
    """
    Requested storage type is not registered
    """


class StorageAuthError(StorageError):
    """
    Authentication with a remote storage backend failed
    """


class StorageConnectionError(StorageError):
    """
    Could not reach the remote storage backend
    """


class DetectionError(Exception):
    """
    Base class for platform detection errors
    """


class DaemonConnectionError(Exception):
    """
    CLI could not reach the daemon (not running, stale runtime file, etc.)
    """


class GameNotFoundError(Exception):
    """
    Referenced game entry does not exist in metadata
    """
