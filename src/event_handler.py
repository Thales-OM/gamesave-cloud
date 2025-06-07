from watchdog.events import FileSystemEventHandler
from src.logger import LoggerFactory


logger = LoggerFactory.getLogger(__name__)


class MyHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            logger.info(f'Modified: {event.src_path}')
            # Implement your action here
    def on_created(self, event):
        if not event.is_directory:
            logger.info(f'Created: {event.src_path}')
            # Implement your action here
    def on_deleted(self, event):
        if not event.is_directory:
            logger.info(f'Deleted: {event.src_path}')
            # Implement your action here
    def on_moved(self, event):
        if not event.is_directory:
            logger.info(f'Moved: {event.src_path} to {event.dest_path}')
            # Implement your action here
