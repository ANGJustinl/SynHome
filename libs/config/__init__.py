"""
SynHome Configuration Management - Simplified

Modern configuration using Pydantic v2 BaseSettings.
"""

from .models import AppSettings, LoggingConfig, DeviceConfig, ZhipuAIConfig
from .loader import load_config, save_config, validate_config_file

__all__ = [
    "AppSettings",
    "LoggingConfig",
    "DeviceConfig",
    "ZhipuAIConfig",
    "load_config",
    "save_config",
    "validate_config_file",
]