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


class GitError(BaseException):
    """
    Base class for errors when working with Git
    """
