# StockGuard Configuration & Environment Management
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "StockGuard"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Environment
    ENVIRONMENT: str = Field(default="development")
    
    # Database Settings
    # Supports PostgreSQL as primary, with SQLite as seamless fallback if PG is unavailable
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/stockguard"
    )
    FALLBACK_DATABASE_URL: str = Field(
        default="sqlite:///./stockguard.db"
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # RabbitMQ Settings
    RABBITMQ_URL: str = Field(
        default="amqp://guest:guest@localhost:5672/"
    )
    RABBITMQ_ENABLED: bool = True
    RABBITMQ_EXCHANGE: str = "stockguard.topic"
    RABBITMQ_DLQ_EXCHANGE: str = "stockguard.dlq"
    RABBITMQ_RETRY_LIMIT: int = 3
    
    # Business Logic Defaults
    DEFAULT_RESERVATION_TTL_SECONDS: int = 600  # 10 minutes
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    EXPIRATION_POLL_INTERVAL_SECONDS: float = 2.0
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    
    # Dashboard Settings
    DASHBOARD_TITLE: str = "StockGuard Enterprise Inventory Control"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
