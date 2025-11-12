"""
Simplified SynHome Configuration using Pydantic v2

Modern, type-safe configuration management with minimal complexity.
"""

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path


class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    file_path: Optional[str] = "logs/app.log"
    max_file_size: str = "10 MB"
    backup_count: int = 5
    console_output: bool = True


class ZhipuAIConfig(BaseModel):
    """ZhipuAI LLM configuration."""
    enabled: bool = False
    api_key: Optional[str] = None
    model: str = "chatglm-turbo"
    base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    @field_validator('api_key')
    def validate_api_key(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError("API key is required when ZhipuAI is enabled")
        return v


class DeviceConfig(BaseModel):
    """Device configuration matching original format."""
    id: str
    name: str
    type: str
    capabilities: Dict[str, Dict[str, Any]]  # Original expects dict, not list


class AppSettings(BaseSettings):
    """Main application settings using Pydantic v2 BaseSettings."""

    # Core application settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Logging configuration
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # External integrations
    zhipuai: ZhipuAIConfig = Field(default_factory=ZhipuAIConfig)

    # Device configuration
    devices: List[DeviceConfig] = Field(default_factory=list)

    # Additional fields from original config
    adapters: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    physical_devices: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Additional settings
    app_name: str = "SynHome"
    version: str = "1.0.0"

    class Config:
        """Pydantic v2 configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "allow"  # Allow extra fields to match original flexibility

    @field_validator('debug')
    def set_debug_from_environment(cls, v, info):
        """Automatically enable debug in development environment."""
        if info.data.get('environment') == Environment.DEVELOPMENT:
            return True
        return v

    @field_validator('port')
    def validate_port(cls, v):
        """Validate port number."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration dictionary."""
        return {
            "level": self.logging.level.value,
            "format": self.logging.format,
            "file_path": self.logging.file_path,
            "console_output": self.logging.console_output,
        }

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT