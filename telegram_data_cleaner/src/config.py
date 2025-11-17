"""
Application configuration using Pydantic Settings.
"""
from typing import List
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://user:pass@localhost:5432/telegram_data",
        description="PostgreSQL connection string"
    )
    database_pool_size: int = Field(default=20, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=50)

    # Redis Configuration
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )
    redis_cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")

    # API Configuration
    api_url: str = Field(
        default="http://103.75.197.239:3000/api/all-messages",
        description="Telegram data API endpoint"
    )
    api_token: str = Field(
        default="telegramreader-api-token-2025",
        description="Bearer token for API authentication"
    )
    api_timeout: int = Field(default=30, ge=5, le=300, description="API timeout in seconds")

    # Polling Configuration
    polling_interval: int = Field(
        default=180,
        ge=60,
        le=3600,
        description="Polling interval in seconds"
    )
    batch_size: int = Field(default=100, ge=10, le=1000, description="Batch size for processing")

    # Application Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    history_days: int = Field(
        default=15,
        ge=1,
        le=365,
        description="Number of days to keep message history"
    )
    environment: str = Field(default="development", description="Environment name")

    # FastAPI Configuration
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, ge=1024, le=65535, description="API server port")
    api_workers: int = Field(default=4, ge=1, le=16, description="Number of API workers")

    # Security
    secret_key: str = Field(
        default="change-this-secret-key-in-production",
        description="Secret key for encryption"
    )
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="CORS allowed origins (comma-separated)"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level value."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v_upper

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins into a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def database_url_str(self) -> str:
        """Get database URL as string."""
        return str(self.database_url)

    @property
    def redis_url_str(self) -> str:
        """Get Redis URL as string."""
        return str(self.redis_url)

    @property
    def api_headers(self) -> dict[str, str]:
        """Generate API headers with bearer token."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }


# Global settings instance
settings = Settings()
