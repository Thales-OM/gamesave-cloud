class AvailablePortNotFoundError(BaseException):
    """
    No available port was found to host the daemon process server
    """


class ControllerCallError(BaseException):
    """
    An invalid request was made to the Controller
    """


class MetadataError(BaseException):
    """
    Base class for errors during Metadata initialization/operations
    """


class MetadataMigrationError(MetadataError):
    """
    Failed to migrate an old metadata schema to the current one
    """


class EngineError(BaseException):
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


class StorageError(BaseException):
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


class DetectionError(BaseException):
    """
    Base class for platform detection errors
    """


class DaemonConnectionError(BaseException):
    """
    CLI could not reach the daemon (not running, stale runtime file, etc.)
    """


class GameNotFoundError(BaseException):
    """
    Referenced game entry does not exist in metadata
    """
