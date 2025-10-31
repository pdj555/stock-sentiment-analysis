"""Configuration management using Pydantic settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Stock Sentiment Analysis API"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # NewsAPI
    newsapi_key: str

    # Cache Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    cache_enabled: bool = False
    cache_ttl: int = 3600

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


settings = Settings()
