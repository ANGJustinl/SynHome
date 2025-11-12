"""
SynHome Configuration Management Module

Provides type-safe configuration management using Pydantic v2.
"""

from .models import AppSettings
from .loader import load_config
from .validator import validate_config
from .legacy import migrate_config_file

__all__ = [
    "AppSettings",
    "load_config",
    "validate_config",
    "migrate_config_file",
]