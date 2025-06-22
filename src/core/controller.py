from typing import List, Dict, Optional
from enum import Enum
from pydantic import DirectoryPath
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from src.models.tracked_directory import TrackedDirectory
from src.core.event_handler import TrackedDirectoryHandler
from src.exceptions import ControllerCallError
from src.models.metadata import Metadata
from src.logger import LoggerFactory


logger = LoggerFactory.getLogger(__name__)


class Status(Enum):
    NOT_INITIALIZED = "not_initialized"
    INITIALIZED = "initialized"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ControlPair:
    directory: TrackedDirectory
    observer: Optional[BaseObserver] = None

    def __init__(
        self, dir: TrackedDirectory, obs: Optional[BaseObserver] = None
    ):
        self.directory = dir
        self.observer = obs


class DirectoryController:
    directories: Dict[DirectoryPath, ControlPair] = dict()
    metadata: Optional[Metadata] = None
    status: Status = Status.NOT_INITIALIZED

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(DirectoryController, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        metadata: Optional[Metadata] = None,
        directories: Optional[List[TrackedDirectory]] = None,
    ):
        if self.status != Status.NOT_INITIALIZED:
            logger.warning("Tred to reinitialize the Controller. Skipping.")
            return

        self.directories: Dict[DirectoryPath, ControlPair] = dict()
        self.metadata = None

        if not (metadata or directories):
            raise ValueError(
                "Neither Metadata, nor directories were provided to Controller"
            )

        if metadata and directories:
            logger.warning(
                "Both Metadata and directories provided \
                           to Controller. Prioritizing Metadata object."
            )

        if metadata:
            self.metadata = metadata
            for directory in metadata.directories:
                self.add_directory(dir=directory)
        else:
            for directory in directories:
                self.add_directory(dir=directory)

        self.status = Status.INITIALIZED

    def add_directory(self, dir: TrackedDirectory) -> None:
        """Start watching a new directory"""
        if dir.path in self.directories:
            logger.warning(
                "Tried adding an already present directory to the Controller"
            )
            return

        self.directories[dir.path] = ControlPair(dir=dir)

        if self.metadata:
            self.metadata.add_directory(dir=dir)
            self.metadata.save_to_disk()

    def start_watching_directory(self, dir: TrackedDirectory) -> None:
        if dir.path not in self.directories:
            logger.warning(
                "Controller tried starting watching a directory \
                    that was not initialized. Initializing automatically."
            )
            self.add_directory(dir=dir)

        if self.directories[dir.path].observer:
            logger.warning(
                "Controller tried to start watching a directory \
                    with an observer already present. Aborting."
            )
            return

        observer = Observer()
        event_handler = TrackedDirectoryHandler()

        observer.schedule(event_handler, dir.path, recursive=True)
        observer.start()
        self.directories[dir.path].observer = observer

        logger.info(f"Started watching directory: {dir.path}")

    def start_all(self) -> None:
        self.status = Status.STARTING

        for pair in self.directories.values():
            self.start_watching_directory(dir=pair.directory)

        self.status = Status.STARTED

    def stop_all(self) -> None:
        if self.status == Status.STOPPING:
            raise ControllerCallError(
                "Tried stopping Controller when already being stopped"
            )
        if self.status == Status.STOPPED:
            raise ControllerCallError(
                "Tried stopping Controller \
                                      when already stopped"
            )
        if self.status == Status.STARTING:
            raise ControllerCallError(
                "Controller currently starting, cannot stop. \
                    Close the application manually if needed"
            )

        self.status = Status.STOPPING

        while self.directories:
            dir_path, pair = self.directories.popitem()
            if pair.observer:
                pair.observer.stop()
                pair.observer.join()
                logger.debug(f"Stopped observer for: {dir_path}")

        logger.info("All directory watchers have been stopped and removed")

        self.status = Status.STOPPED
