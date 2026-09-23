"""
Central configuration — reads from environment / .env file.
All settings are typed and validated by Pydantic.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "dev-secret-key"
    APP_DEBUG: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- LLM ---
    ACTIVE_LLM: str = "gemini/gemini-1.5-pro"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://abos_user:abos_password@localhost:5432/abos"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Celery ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # --- JWT ---
    JWT_SECRET_KEY: str = "dev-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- OAuth2 ---
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # --- MLflow ---
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "abos-experiments"

    # --- Agent defaults ---
    AGENT_MAX_RETRIES: int = 3
    AGENT_TIMEOUT_SECONDS: int = 120
    SCHEDULER_WINDOW_SIZE: int = 50  # rolling window for performance tracking


import os

settings = Settings()

if settings.GEMINI_API_KEY and "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
if settings.OPENAI_API_KEY and "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
