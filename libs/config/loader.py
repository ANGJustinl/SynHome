"""
Configuration loading utilities for SynHome.

Provides simple configuration loading with Pydantic validation and legacy format support.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from loguru import logger

from .models import AppSettings
from .validator import ConfigValidator
from .legacy import is_legacy_config, migrate_config_file as legacy_migrator


def load_config(
    config_file: Optional[Union[str, Path]] = None,
    **overrides
) -> AppSettings:
    """
    Load configuration from file or create default settings.

    Args:
        config_file: Optional configuration file path
        **overrides: Configuration overrides

    Returns:
        Loaded and validated AppSettings
    """
    try:
        # Load base configuration
        if config_file:
            config_path = Path(config_file)
            if config_path.exists():
                config_data = _load_config_file(config_path)
            else:
                logger.warning(f"Configuration file not found: {config_path}")
                config_data = {}
        else:
            # Try default locations
            config_data = _try_load_default_config()

        # Apply overrides
        if overrides:
            config_data.update(overrides)

        # Handle legacy format migration
        if is_legacy_config(config_data):
            logger.info("Detected legacy configuration format, migrating...")
            config_data, warnings = legacy_migrator(config_data)
            for warning in warnings:
                logger.warning(f"Migration warning: {warning}")

        # Validate and create AppSettings
        validator = ConfigValidator()
        is_valid, errors = validator.validate_config_data(config_data)

        if not is_valid:
            error_msg = f"Configuration validation failed: {'; '.join(errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        app_settings = AppSettings(**config_data)
        logger.info("Configuration loaded successfully")
        return app_settings

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise


def validate_config(config_data: Dict[str, Any]) -> bool:
    """
    Validate configuration data.

    Args:
        config_data: Configuration dictionary to validate

    Returns:
        True if configuration is valid
    """
    validator = ConfigValidator()
    is_valid, errors = validator.validate_config_data(config_data)

    if not is_valid:
        logger.error(f"Configuration validation failed: {'; '.join(errors)}")
        return False

    return True


def _load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load configuration from file."""
    if config_path.suffix.lower() in ['.yaml', '.yml']:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    elif config_path.suffix.lower() == '.json':
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise ValueError(f"Unsupported configuration file format: {config_path.suffix}")


def _try_load_default_config() -> Dict[str, Any]:
    """Try to load configuration from default locations."""
    default_locations = [
        "config/base.yaml",
        "config.yaml",
        "config.yml"
    ]

    for location in default_locations:
        config_path = Path(location)
        if config_path.exists():
            logger.info(f"Loading default configuration from: {config_path}")
            return _load_config_file(config_path)

    # Return minimal default configuration
    logger.warning("No configuration file found, using defaults")
    return {
        "environment": "development",
        "debug": True,
        "host": "localhost",
        "port": 8000,
        "logging": {
            "level": "INFO",
            "console_output": True
        },
        "zhipuai": {"enabled": False},
        "hot_reload": {"enabled": False},
        "devices": [],
        "adapters": []
    }