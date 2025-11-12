"""
Configuration models for SynHome using Pydantic v2.

These models provide type-safe configuration management with validation,
environment variable support, and clear error messages.
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Log levels matching Python logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogConfig(BaseModel):
    """Logging configuration model."""
    level: LogLevel = LogLevel.INFO
    format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        description="Log message format string"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to log file (if logging to file)"
    )
    max_size: str = Field(
        default="100 MB",
        description="Maximum log file size before rotation"
    )
    retention: str = Field(
        default="30 days",
        description="How long to keep log files"
    )
    compression: str = Field(
        default="zip",
        description="Compression format for rotated logs"
    )
    rotation: str = Field(
        default="1 day",
        description="Log file rotation schedule"
    )
    serialize: bool = Field(
        default=False,
        description="Whether to serialize logs as JSON"
    )
    enqueue: bool = Field(
        default=True,
        description="Whether to use async log writing"
    )
    console_output: Optional[bool] = Field(
        default=None,
        description="Whether to output logs to console"
    )

    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        return LogLevel(v.upper())


class ZhipuAIConfig(BaseModel):
    """ZhipuAI LLM configuration model."""
    enabled: bool = Field(
        default=False,
        description="Whether ZhipuAI LLM integration is enabled"
    )
    api_key: str = Field(
        description="ZhipuAI API key",
        min_length=10
    )
    model: str = Field(
        default="chatglm-turbo",
        description="ZhipuAI model to use"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature parameter for generation"
    )

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError('API key must be at least 10 characters long')
        return v


class HotReloadConfig(BaseModel):
    """Hot reload configuration model."""
    enabled: bool = Field(
        default=True,
        description="Whether hot reload is enabled"
    )
    watch_files: List[str] = Field(
        default_factory=lambda: ["*.yaml", "*.yml", "*.json"],
        description="File patterns to watch for changes"
    )
    debounce_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Debounce time for file changes in seconds"
    )
    reloadable_sections: List[str] = Field(
        default_factory=lambda: ["logging", "zhipuai", "device_groups", "scenes"],
        description="Configuration sections that can be hot reloaded"
    )


class AppSettings(BaseSettings):
    """Main application settings with environment variable support."""
    model_config = SettingsConfigDict(
        env_prefix="SYNHOME_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid"
    )

    # Core settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    # Logging
    logging: LogConfig = LogConfig()

    # LLM Integration
    zhipuai: Optional[ZhipuAIConfig] = None

    # Hot Reload
    hot_reload: HotReloadConfig = HotReloadConfig()

    # Feature Flags
    features: Dict[str, bool] = Field(
        default_factory=dict,
        description="Feature flags for enabling/disabling functionality"
    )

    # Additional configuration (loaded from YAML)
    devices_file: Optional[str] = Field(
        default="config/demo.yaml",
        description="Path to devices configuration file"
    )

    # Security
    secret_key: Optional[str] = Field(
        default=None,
        description="Secret key for session management"
    )

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if v < 1 or v > 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v

    def get_log_file_path(self) -> str:
        """Get the effective log file path, handling None values."""
        if self.logging.file_path:
            return self.logging.file_path

        # Default log file paths by environment
        env_defaults = {
            Environment.PRODUCTION: "/var/log/synhome/app.log",
            Environment.TESTING: "logs/test.log",
            Environment.DEVELOPMENT: "logs/app.log"
        }
        return env_defaults.get(self.environment, "logs/app.log")

    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION