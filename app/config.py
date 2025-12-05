"""
Configuration management following 12-factor app principles.
All settings are loaded from environment variables with sensible defaults.
"""
import os
from typing import Optional


class Config:
    """Application configuration loaded from environment variables."""
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Security
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/data/app.db")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # json or text
    
    # Pagination
    DEFAULT_PAGE_LIMIT: int = int(os.getenv("DEFAULT_PAGE_LIMIT", "50"))
    MAX_PAGE_LIMIT: int = int(os.getenv("MAX_PAGE_LIMIT", "100"))
    
    # Metrics
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate critical configuration.
        Returns True if valid, False otherwise.
        """
        if not cls.WEBHOOK_SECRET:
            return False
        return True
    
    @classmethod
    def is_ready(cls) -> bool:
        """Check if application is ready (has required config)."""
        return bool(cls.WEBHOOK_SECRET)


# Note: We don't validate on import to allow /health/ready to check
