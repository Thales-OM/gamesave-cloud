import logging
import sys
from typing import Optional
from src.settings import settings


class LoggerFactory:
    _configured = False
    _handler = None

    @classmethod
    def _create_handler(cls) -> logging.Handler:
        """Create and configure the standard handler."""
        handler = logging.StreamHandler(stream=sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        return handler

    @classmethod
    def _configure_logger(cls, logger: logging.Logger) -> None:
        """Configure a logger instance with the standard settings."""
        if cls._handler is None:
            cls._handler = cls._create_handler()

        log_level = getattr(logging, settings.logging.log_level)

        logger.setLevel(log_level)
        logger.addHandler(cls._handler)

        # Prevent duplicate logs from propagating to root logger
        logger.propagate = False

    @classmethod
    def getLogger(cls, name: Optional[str] = None) -> logging.Logger:
        """Get a configured logger instance."""
        logger = logging.getLogger(name)
        cls._configure_logger(logger)
        return logger
