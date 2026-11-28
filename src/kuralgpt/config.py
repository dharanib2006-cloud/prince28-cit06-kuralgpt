"""Application configuration and environment settings."""

import os
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
    git_sha: str = Field(default_factory=lambda: os.getenv("RENDER_GIT_COMMIT", "dev"))

    # LLM gateway (Day 8). Keys default to empty so tests and CI never need them.
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_primary_model: str = "gemini-3.6-flash"
    llm_fallback_model: str = "openai/gpt-oss-20b"

    # Both providers speak the OpenAI API, so any compatible server works (Ollama, a test fake).
    llm_primary_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_fallback_base_url: str = "https://api.groq.com/openai/v1"

    llm_timeout_seconds: float = 30.0
    usd_inr: float = 95.0  # rupees per US dollar, for cost estimates
    prompts_dir: Path = Path("prompts")

    # Queue and worker (Day 10). One Redis; the worker is a second process
    # running the same code.
    redis_url: str = "redis://localhost:6379"
    manifest_file: Path = Path("data/manifest.jsonl")
    admin_token: str = ""
    worker_in_api: bool = False
    ingest_concurrency: int = 2
    ingest_rpm: float = 12.0
    ingest_job_timeout: int = 300
    ingest_max_tries: int = 3

    log_level: str = "INFO"
    data_file: Path = Path("data/sample_records.json")

    # PostgreSQL connection URL. Keep the password out of logs.
    database_url: str | None = Field(default=None, repr=False)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
