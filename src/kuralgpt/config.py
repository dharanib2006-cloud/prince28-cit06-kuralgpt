"""Application configuration and environment settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables or the .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "kuralgpt"
    app_env: str = Field(pattern="^(local|ci|production)$")
    # The commit this image was built from. CI sets it.
    git_sha: str = "dev"
    log_level: str = "INFO"
    data_file: Path = Path("data/sample_records.json")

    # PostgreSQL connection URL. Keep the password out of logs.
    database_url: str | None = Field(default=None, repr=False)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
