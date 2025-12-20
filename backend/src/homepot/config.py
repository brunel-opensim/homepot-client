"""Configuration management for HOMEPOT Client.

This module provides configuration loading from environment variables
and settings files using Pydantic Settings.
"""

from typing import Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    url: str = Field(
        default=(
            "postgresql://homepot_user:homepot_dev_password@"
            "localhost:5432/homepot_db"
        ),
        description="Database URL (PostgreSQL)",
    )
    echo_sql: bool = Field(default=False, description="Enable SQL query logging")
    pool_size: int = Field(default=5, description="Database connection pool size")
    max_overflow: int = Field(
        default=10, description="Maximum connection pool overflow"
    )


class AuthSettings(BaseSettings):
    """Authentication configuration settings."""

    secret_key: str = Field(
        default="homepot-dev-secret-change-in-production",
        description="Secret key for JWT token generation",
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration time in minutes"
    )
    api_key_header: str = Field(
        default="X-API-Key", description="Header name for API key authentication"
    )


class RedisSettings(BaseSettings):
    """Redis configuration for job queues and caching."""

    url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    max_connections: int = Field(default=10, description="Maximum Redis connections")
    socket_timeout: int = Field(
        default=30, description="Redis socket timeout in seconds"
    )


class PushNotificationSettings(BaseSettings):
    """Push notification configuration."""

    enabled: bool = Field(default=True, description="Enable push notifications")
    default_ttl: int = Field(
        default=300, description="Default TTL for push notifications in seconds"
    )
    max_payload_size: int = Field(
        default=4096, description="Maximum push notification payload size in bytes"
    )
    collapse_key_prefix: str = Field(
        default="homepot", description="Prefix for push notification collapse keys"
    )

    # Web Push (VAPID) Configuration
    vapid_private_key: Optional[str] = Field(
        default=None, description="VAPID private key for Web Push"
    )
    vapid_public_key: Optional[str] = Field(
        default=None, description="VAPID public key for Web Push"
    )
    vapid_subject: Optional[str] = Field(
        default=None, description="VAPID subject (mailto or URL)"
    )

    # WNS (Windows) Configuration
    wns_package_sid: Optional[str] = Field(
        default=None, description="Windows Package SID"
    )
    wns_client_secret: Optional[str] = Field(
        default=None, description="WNS Client Secret"
    )


class DeviceSettings(BaseSettings):
    """Device management configuration."""

    health_check_interval: int = Field(
        default=60, description="Health check interval in seconds"
    )
    health_check_timeout: int = Field(
        default=10, description="Health check timeout in seconds"
    )
    device_offline_threshold: int = Field(
        default=300, description="Seconds before marking device as offline"
    )
    max_concurrent_jobs: int = Field(
        default=10, description="Maximum concurrent jobs per device"
    )


class WebSocketSettings(BaseSettings):
    """WebSocket configuration for real-time communication."""

    enabled: bool = Field(default=True, description="Enable WebSocket endpoints")
    ping_interval: int = Field(
        default=20, description="WebSocket ping interval in seconds"
    )
    ping_timeout: int = Field(
        default=10, description="WebSocket ping timeout in seconds"
    )
    max_connections: int = Field(
        default=100, description="Maximum concurrent WebSocket connections"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    level: str = Field(
        default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    file_path: Optional[str] = Field(
        default=None, description="Log file path (None for stdout only)"
    )
    max_size_mb: int = Field(default=10, description="Maximum log file size in MB")
    backup_count: int = Field(
        default=5, description="Number of log file backups to keep"
    )


class CorsSettings(BaseSettings):
    """Existing fields."""

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:3000",
            "http://192.168.0.112:3000",
            "http://192.168.0.112:3001",
            "http://192.168.0.112:8080",
            "http://localhost:5173/",
            "http://localhost:5173",
            "http://192.168.0.253:5173",
        ],
        description="Allowed CORS origins",
    )


class Settings(BaseSettings):
    """Main application settings."""

    # Application info
    app_name: str = Field(default="HOMEPOT Client", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")
    cors: CorsSettings = Field(default_factory=CorsSettings)
    environment: str = Field(
        default="development",
        description="Environment (development, testing, production)",
    )

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Server host")  # nosec B104
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")

    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    push: PushNotificationSettings = Field(default_factory=PushNotificationSettings)
    devices: DeviceSettings = Field(default_factory=DeviceSettings)
    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # Mobivisor API settings
    mobivisor_api_url: str = Field(
        default="https://mydd.mobivisor.com/",
        description="Mobivisor API endpoint URL",
    )
    mobivisor_api_token: Optional[str] = Field(
        default=None, description="Mobivisor API Bearer token"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment/files."""
    global _settings
    _settings = Settings()
    return _settings


# Convenience functions for accessing specific settings
def get_database_url() -> str:
    """Get database URL."""
    return get_settings().database.url


def get_redis_url() -> str:
    """Get Redis URL."""
    return get_settings().redis.url


def is_debug() -> bool:
    """Check if debug mode is enabled."""
    return get_settings().debug


def get_secret_key() -> str:
    """Get JWT secret key."""
    return get_settings().auth.secret_key


def get_mobivisor_api_config() -> Dict[str, Optional[str]]:
    """Get Mobivisor API URL and token.

    Returns:
        Dict containing mobivisor_api_url and mobivisor_api_token
    """
    settings = get_settings()
    return {
        "mobivisor_api_url": settings.mobivisor_api_url,
        "mobivisor_api_token": settings.mobivisor_api_token,
    }
