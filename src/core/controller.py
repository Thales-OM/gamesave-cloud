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

    def __init__(self, dir: TrackedDirectory, obs: Optional[BaseObserver] = None):
        self.directory = dir
        self.observer = obs


class DirectoryController:
    observers: Dict[DirectoryPath, BaseObserver] = dict()
    metadata: Metadata
    status: Status = Status.NOT_INITIALIZED

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(DirectoryController, cls).__new__(cls)
        return cls._instance

    def __init__(self, metadata: Optional[Metadata]):
        if self.status != Status.NOT_INITIALIZED:
            logger.warning("Tred to reinitialize the Controller. Skipping.")
            return

        self.metadata = metadata
        for directory in metadata.directories:
            self.add_directory(dir=directory)
        self.metadata.save_to_disk()

        self.status = Status.INITIALIZED

    def add_directory(
        self,
        dir: TrackedDirectory,
    ) -> None:
        """Add directory to current Metadata"""
        try:
            self.metadata.add_directory(dir=dir)
        except Exception as ex:
            logger.error(
                f"Failed to add directory to Metadata: \n{ex}"
            )
    
    def delete_directory(
            self,
            dir: TrackedDirectory
    ) -> None:
        """Remove directory from current Metadata"""
        # Remove from observers if needed
        self.stop_observer(dir=dir)

        try:
            self.metadata.delete_directory(path=dir.path)
        except Exception as ex:
            logger.error(
                f"Failed to delete directory from Metadata: \n{ex}"
            ) 

    def start_observer(self, dir: TrackedDirectory) -> None:
        if not self.metadata.get_directory_by_path(path=dir.path):
            logger.warning(
                "Tried starting observer on a directory not \
                           present in Metadata. Automatically adding..."
            )
            self.add_directory(dir=dir)

        if self.observers[dir.path]:
            logger.warning(
                "Controller tried to start watching a directory \
                    with an observer already present. Aborting."
            )
            return

        observer = Observer()
        event_handler = TrackedDirectoryHandler()

        observer.schedule(event_handler, dir.path, recursive=True)
        observer.start()
        self.observers[dir.path] = observer

        logger.info(f"Started watching directory: {dir.path}")

    def stop_observer(self, dir: TrackedDirectory) -> None:
        observer = self.observers.pop(dir.path, None)
        if observer:
            observer.stop()
            observer.join()
            logger.debug(f"Stopped observer for: {dir.path}")

    def start_all(self) -> None:
        self.status = Status.STARTING

        for dir in self.metadata.get_all_directories():
            self.start_observer(dir=dir)

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

        while self.observers:
            dir_path, observer = self.observers.popitem()
            observer.stop()
            observer.join()
            logger.debug(f"Stopped observer for: {dir_path}")

        logger.info("All directory watchers have been stopped and removed")

        self.status = Status.STOPPED
