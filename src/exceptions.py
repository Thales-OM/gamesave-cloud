class AvailablePortNotFoundError(BaseException):
    """
    No available port was found to host the daemon process server
    """


class ControllerCallError(BaseException):
    """
    An invalid request was made to the Controller
    """
