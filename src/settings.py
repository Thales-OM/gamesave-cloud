from pydantic import Field, model_validator, DirectoryPath
from pydantic_settings import BaseSettings
from src.constraints import (
    DEFAULT_LOG_LEVEL,
    DEFAULT_LIMIT_SAVE_INTERVALS,
    DEFAULT_SAVE_COOLDOWN_SEC,
    DEFAULT_MASTER_BRANCH,
    METADATA_STORAGE_FILEPATH,
    DAEMON_PORT_RANGE_MIN,
    DAEMON_PORT_RANGE_MAX,
)


class DaemonSettings(BaseSettings):
    port_range_min: int = DAEMON_PORT_RANGE_MIN
    port_range_max: int = DAEMON_PORT_RANGE_MAX


class SaveStateSettings(BaseSettings):
    limit_save_intervals: bool = DEFAULT_LIMIT_SAVE_INTERVALS
    save_cooldown_sec: int = DEFAULT_SAVE_COOLDOWN_SEC


class MetadataSettings(BaseSettings):
    storage_filepath: DirectoryPath = METADATA_STORAGE_FILEPATH


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
                f"Invalid log level. \
                             Must be one of {valid_levels}"
            )
        return self


class Settings(BaseSettings):
    daemon: DaemonSettings = DaemonSettings()
    save_state: SaveStateSettings = SaveStateSettings()
    metadata: MetadataSettings = MetadataSettings()
    git: GitSettings = GitSettings()
    logging: LoggingSettings = LoggingSettings()


settings = Settings()
