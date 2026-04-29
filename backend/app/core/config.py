"""
Application configuration module.
Loads settings from environment variables and provides typed configuration.
"""
import secrets
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "GYSBIN PHARMACY ANNEX"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_BACKEND: str = "postgresql"  # postgresql
    DATABASE_URL: Optional[str] = None
    SQLITE_DATABASE_PATH: str = "./pharma_pos.db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "pharma_pos"
    POSTGRES_USER: str = "pharma_user"
    POSTGRES_PASSWORD: str = ""
    ALLOW_SQLITE_IN_PRODUCTION: bool = False

    # Security
    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator(
        "BACKEND_CORS_ORIGINS",
        "AI_WEEKLY_REPORT_EMAIL_RECIPIENTS",
        "AI_WEEKLY_REPORT_TELEGRAM_CHAT_IDS",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def assemble_comma_separated_list(cls, v):
        """Parse comma-separated environment values into lists."""
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                # Handle JSON-like env strings without requiring callers to
                # switch formats between Docker and local installs.
                v = v[1:-1].replace('"', "").replace("'", "")
            return [i.strip() for i in v.split(",")]
        return v

    # Notifications
    ENABLE_EMAIL_NOTIFICATIONS: bool = False
    N8N_WEBHOOK_URL: Optional[str] = None


    TIMEZONE: str = "Africa/Accra"

    # Scheduler
    ENABLE_BACKGROUND_SCHEDULER: bool = True
    EXPIRY_CHECK_HOUR: int = 9
    LOW_STOCK_CHECK_HOUR: int = 10

    # Cloud sync - Supabase Postgres target through backend/edge ingestion API
    CLOUD_SYNC_ENABLED: bool = False
    CLOUD_SYNC_INGEST_URL: Optional[str] = None
    CLOUD_SYNC_API_TOKEN: Optional[str] = None
    CLOUD_SYNC_DEVICE_UID: Optional[str] = None
    CLOUD_SYNC_ORGANIZATION_ID: Optional[int] = None
    CLOUD_SYNC_BRANCH_ID: Optional[int] = None
    CLOUD_SYNC_BATCH_SIZE: int = 50
    CLOUD_SYNC_TIMEOUT_SECONDS: int = 15
    CLOUD_SYNC_MAX_RETRIES: int = 10
    CLOUD_SYNC_INTERVAL_MINUTES: int = 5

    # AI manager assistant provider. Keys remain server-side only.
    AI_MANAGER_PROVIDER: str = "deterministic"  # deterministic, openai, claude, groq
    AI_MANAGER_MODEL: Optional[str] = None
    AI_MANAGER_TIMEOUT_SECONDS: int = 20
    AI_MANAGER_MAX_TOKENS: int = 700
    AI_WEEKLY_REPORTS_ENABLED: bool = False
    AI_WEEKLY_REPORT_DAY: str = "sun"
    AI_WEEKLY_REPORT_HOUR: int = 19
    AI_WEEKLY_REPORT_MINUTE: int = 0
    AI_WEEKLY_REPORT_DELIVERY_ENABLED: bool = False
    AI_WEEKLY_REPORT_EMAIL_ENABLED: bool = False
    AI_WEEKLY_REPORT_EMAIL_RECIPIENTS: List[str] = []
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "Pharmacy POS"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    AI_WEEKLY_REPORT_TELEGRAM_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    AI_WEEKLY_REPORT_TELEGRAM_CHAT_IDS: List[str] = []
    AI_WEEKLY_REPORT_DELIVERY_TIMEOUT_SECONDS: int = 15
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Business Rules
    LOW_STOCK_THRESHOLD: int = 10
    EXPIRY_WARNING_DAYS: int = 30
    DEAD_STOCK_DAYS: int = 90

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 5242880  # 5MB

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    @model_validator(mode="after")
    def finalize_settings(self):
        """Build derived settings and enforce production-safe defaults."""
        environment = self.ENVIRONMENT.lower()
        backend = self.DATABASE_BACKEND.lower()

        if backend != "postgresql":
            raise ValueError(
                "Unsupported DATABASE_BACKEND. This production build only supports PostgreSQL."
            )

        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        if not self.SECRET_KEY:
            if environment == "production":
                raise ValueError("SECRET_KEY must be set in production.")
            self.SECRET_KEY = secrets.token_urlsafe(32)

        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
