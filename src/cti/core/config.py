"""Application configuration via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ── PostgreSQL ───────────────────────────────────────────────────────
    POSTGRES_USER: str = "cti"
    POSTGRES_PASSWORD: SecretStr = SecretStr("change-me")
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cti"

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Feed system ──────────────────────────────────────────────────────
    FEED_ENCRYPTION_KEY: SecretStr = SecretStr("change-me")
    FEED_DEFAULT_TIMEOUT: int = 30
    FEED_MAX_RETRIES: int = 3

    # ── Confidence decay ─────────────────────────────────────────────────
    CONFIDENCE_DECAY_ENABLED: bool = True
    CONFIDENCE_DECAY_DAYS: int = 30
    CONFIDENCE_DECAY_RATE: int = 5
    CONFIDENCE_DECAY_FLOOR: int = 10
    CONFIDENCE_DECAY_INTERVAL_HOURS: int = 6

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # ── Feed API keys (optional) ─────────────────────────────────────────
    ABUSEIPDB_API_KEY: str = ""
    OTX_API_KEY: str = ""
    GREYNOISE_API_KEY: str = ""
    URLSCAN_API_KEY: str = ""

    # ── Computed database URLs ───────────────────────────────────────────

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        """Sync database URL for Alembic migrations (psycopg driver)."""
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Async database URL for the application (psycopg async driver)."""
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return (
            f"postgresql+psycopg_async://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (reads .env once)."""
    return Settings()
