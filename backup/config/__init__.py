"""
SynHome Configuration Management Module

This module provides type-safe configuration management for the SynHome
smart home control system using Pydantic v2 with environment variable support.
"""

from .models import AppSettings, LogConfig, ZhipuAIConfig, HotReloadConfig
from .loader import ConfigLoader
from .validator import ConfigValidator
from .legacy import LegacyConfigAdapter

__all__ = [
    "AppSettings",
    "LogConfig",
    "ZhipuAIConfig",
    "HotReloadConfig",
    "ConfigLoader",
    "ConfigValidator",
    "LegacyConfigAdapter",
]

__version__ = "1.0.0"