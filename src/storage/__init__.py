from src.storage.base import (  # noqa: F401
    RemoteStorage,
    STORAGE_REGISTRY,
    create_storage,
    get_storage_class,
    register_storage,
)

# Importing builtin backends triggers their @register_storage decorators.
from src.storage.filesystem import FilesystemStorage  # noqa: F401,E402
from src.storage.s3 import S3Storage  # noqa: F401,E402
from src.storage.webdav import WebDAVStorage  # noqa: F401,E402
from src.storage.yandex import YandexDiskStorage  # noqa: F401,E402

# Reserved for phase 2 of remotes:
# from src.storage.gdrive import GoogleDriveStorage  # noqa: E402
