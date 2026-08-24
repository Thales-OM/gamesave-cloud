import os


def _default_app_data_root() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "gamesave-cloud")
    return os.path.join(os.path.expanduser("~"), ".local", "share", "gamesave-cloud")


APP_NAME = "gamesave-cloud"
APP_VERSION = "0.2.0"

# App data root: vault, metadata and runtime files live here
# (never inside game folders)
APP_DATA_ROOT = _default_app_data_root()

METADATA_DIRECTORY_PATH = APP_DATA_ROOT
METADATA_FILENAME = "metadata.json"

REPOS_DIR_NAME = "repos"
RUNTIME_FILENAME = "daemon.json"

DEFAULT_LOG_LEVEL = "INFO"

DEFAULT_LIMIT_SAVE_INTERVALS = True
DEFAULT_SAVE_COOLDOWN_SEC = 300
DEFAULT_QUIET_PERIOD_SEC = 30

DEFAULT_MASTER_BRANCH = "main"
DEFAULT_REMOTE_NAME = "origin"

DAEMON_HOST = "127.0.0.1"
DAEMON_DEFAULT_PORT = 7420
DAEMON_PORT_RANGE_MIN = 1024
DAEMON_PORT_RANGE_MAX = 49151

GIT_AUTHOR_NAME = "gamesave-cloud"
GIT_AUTHOR_EMAIL = "gsc@localhost"

KEYRING_SERVICE = "gamesave-cloud"

METADATA_SCHEMA_VERSION = "0.2.0"
