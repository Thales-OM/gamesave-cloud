from typing import List
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from src.models.tracked_directory import TrackedDirectory
from src.event_handler import TrackedDirectoryHandler
from src.logger import LoggerFactory


logger = LoggerFactory.getLogger(__name__)


class DirectoryController:
    directories: List[TrackedDirectory]
    observers: List[BaseObserver]

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(DirectoryController, cls).__new__(cls)
        return cls._instance

    def __init__(self, directories: List[TrackedDirectory]):
        self.directories: List[TrackedDirectory] = []
        self.observers: List[BaseObserver] = []

        for directory in directories:
            self.add_directory(dir=directory)

    def add_directory(self, dir: TrackedDirectory) -> None:
        """Start watching a new directory"""

        observer = Observer()
        path = dir.path
        event_handler = TrackedDirectoryHandler()

        observer.schedule(event_handler, path, recursive=True)
        observer.start()
        self.observers.append(observer)

        logger.info(f"Started watching directory: {path}")

    def stop_all(self) -> None:
        for observer in self.observers:
            observer.stop()
