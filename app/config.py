"""Configuration settings for the FastAPI application."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./closures.db"

    tracker_token: str = ""
    tracker_queue: str = ""

    admin_api_key: str = ""

    bot_token: str = ""
    bot_url: str = "http://localhost:8080"


settings = Settings()
