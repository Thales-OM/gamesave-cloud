import os
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from src.constants import (
    APP_DATA_ROOT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LIMIT_SAVE_INTERVALS,
    DEFAULT_SAVE_COOLDOWN_SEC,
    DEFAULT_QUIET_PERIOD_SEC,
    DEFAULT_MASTER_BRANCH,
    DAEMON_HOST,
    DAEMON_DEFAULT_PORT,
    METADATA_FILENAME,
    REPOS_DIR_NAME,
)


class DaemonSettings(BaseSettings):
    host: str = DAEMON_HOST
    port: int = DAEMON_DEFAULT_PORT
    runtime_filename: str = "daemon.json"


class SaveStateSettings(BaseSettings):
    limit_save_intervals: bool = DEFAULT_LIMIT_SAVE_INTERVALS
    save_cooldown_sec: int = DEFAULT_SAVE_COOLDOWN_SEC
    quiet_period_sec: int = DEFAULT_QUIET_PERIOD_SEC


class MetadataSettings(BaseSettings):
    directory_path: str = APP_DATA_ROOT
    filename: str = METADATA_FILENAME

    @property
    def filepath(self) -> str:
        return os.path.join(self.directory_path, self.filename)


class VaultSettings(BaseSettings):
    """Root directory holding one repo per tracked game."""

    root: str = APP_DATA_ROOT

    @property
    def repos_path(self) -> str:
        return os.path.join(self.root, REPOS_DIR_NAME)


class GitSettings(BaseSettings):
    master_branch: str = DEFAULT_MASTER_BRANCH


class LoggingSettings(BaseSettings):
    log_level: str = Field(DEFAULT_LOG_LEVEL, env="LOG_LEVEL")

    @model_validator(mode="after")
    def validate_log_level(self):
        valid_levels = (
            "CRITICAL",
            "FATAL",
            "ERROR",
            "WARN",
            "WARNING",
            "INFO",
            "DEBUG",
            "NOTSET",
        )
        if self.log_level not in valid_levels:
            raise ValueError(
                f"Invalid log level. Must be one of {valid_levels}"
            )
        return self


class Settings(BaseSettings):
    app_data_root: str = APP_DATA_ROOT
    daemon: DaemonSettings = DaemonSettings()
    save_state: SaveStateSettings = SaveStateSettings()
    metadata: MetadataSettings = MetadataSettings()
    vault: VaultSettings = VaultSettings()
    git: GitSettings = GitSettings()
    logging: LoggingSettings = LoggingSettings()


settings = Settings()
