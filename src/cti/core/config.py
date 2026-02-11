from functools import lru_cache

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    ENVIRONMENT: str = "development"
    SECRET_KEY: SecretStr = SecretStr("change-me")
    ADMIN_PASSWORD: SecretStr = SecretStr("admin")
    LOG_LEVEL: str = "INFO"

    # PostgreSQL
    POSTGRES_USER: str = "cti"
    POSTGRES_PASSWORD: SecretStr = SecretStr("change-me")
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cti"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # JWT
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # Feed defaults
    FEED_DEFAULT_TIMEOUT: int = 30
    FEED_MAX_RETRIES: int = 3
    FEED_ENCRYPTION_KEY: SecretStr = SecretStr("change-me")

    # SSO - Azure AD (Microsoft 365)
    SSO_AZURE_AD_ENABLED: bool = False
    SSO_AZURE_AD_CLIENT_ID: str = ""
    SSO_AZURE_AD_CLIENT_SECRET: SecretStr = SecretStr("")
    SSO_AZURE_AD_TENANT_ID: str = ""

    # SSO - Google Workspace
    SSO_GOOGLE_ENABLED: bool = False
    SSO_GOOGLE_CLIENT_ID: str = ""
    SSO_GOOGLE_CLIENT_SECRET: SecretStr = SecretStr("")
    SSO_GOOGLE_ALLOWED_DOMAIN: str = ""

    # SSO - Generic OIDC
    SSO_OIDC_ENABLED: bool = False
    SSO_OIDC_CLIENT_ID: str = ""
    SSO_OIDC_CLIENT_SECRET: SecretStr = SecretStr("")
    SSO_OIDC_ISSUER_URL: str = ""
    SSO_OIDC_DISPLAY_NAME: str = "SSO"

    # SSO defaults
    SSO_DEFAULT_ROLE: str = "readonly"
    SSO_AUTO_CREATE_USERS: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return (
            f"postgresql+psycopg_async://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
