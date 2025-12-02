"""
Application configuration module.
Loads settings from environment variables and provides typed configuration.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "PHARMA-POS-AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str = "sqlite:///./pharma_pos.db"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
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

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
