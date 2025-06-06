from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from typing import Optional, Union, Literal
from src.constraints import DEFAULT_LOG_LEVEL


class LoggingSettings(BaseSettings):
    log_level: str = Field(DEFAULT_LOG_LEVEL, env="LOG_LEVEL")

    @model_validator(mode="after")
    def validate_log_level(self):
        valid_levels = ('CRITICAL', 'FATAL', 'ERROR', 'WARN', 'WARNING', 'INFO', 'DEBUG', 'NOTSET')
        if self.log_level not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of {valid_levels}")
        return self

class Settings(BaseSettings):
    logging: LoggingSettings = LoggingSettings()

settings = Settings()
