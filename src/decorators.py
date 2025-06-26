from logging import Logger


def log_exception(logger: Logger):
    """
    Decorator that logs exceptions occurring in Watchdog event handler methods.

    Args:
        logger: Configured logger instance for error logging
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract handler instance from args (self is first argument)
                handler_instance = args[0]

                # Get handler name if available
                handler_name = getattr(
                    handler_instance, "name", "UnnamedHandler"
                )

                # Log exception with contextual information
                logger.error(
                    f"[{handler_name}] Exception in {func.__name__}: {str(e)}",
                    exc_info=True,
                )

        return wrapper

    return decorator
