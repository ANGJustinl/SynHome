"""
Simple configuration loader for SynHome using Pydantic v2.

No complex validation chains, no dependency injection, just clean loading.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Union
from loguru import logger

from .models import AppSettings


def load_config(
    config_file: Optional[Union[str, Path]] = None,
    **overrides
) -> AppSettings:
    """
    Load configuration from file, environment variables, and overrides.

    Simple and clean configuration loading using Pydantic v2 BaseSettings.

    Args:
        config_file: Path to YAML configuration file
        **overrides: Direct configuration overrides

    Returns:
        Validated AppSettings instance
    """
    # Determine config file path
    if config_file is None:
        config_file = os.getenv("SYNHOME_CONFIG_FILE", "config/demo.yaml")

    config_path = Path(config_file)
    config_data = {}

    # Load YAML file if it exists
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load config file {config_path}: {e}")
            raise
    else:
        logger.warning(f"Config file {config_path} not found, using defaults and environment")

    # Apply overrides
    if overrides:
        config_data.update(overrides)
        logger.debug(f"Applied {len(overrides)} configuration overrides")

    # Create AppSettings - Pydantic handles environment variables automatically
    try:
        settings = AppSettings(**config_data)
        logger.info(
            f"Configuration loaded - Environment: {settings.environment.value}, "
            f"Debug: {settings.debug}, Port: {settings.port}"
        )
        return settings
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


def save_config(settings: AppSettings, config_file: Union[str, Path]) -> None:
    """
    Save configuration to YAML file.

    Args:
        settings: AppSettings instance to save
        config_file: Path to save configuration
    """
    config_path = Path(config_file)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                settings.model_dump(exclude_none=True, by_alias=False),
                f,
                default_flow_style=False,
                allow_unicode=True,
                indent=2
            )
        logger.info(f"Configuration saved to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save config to {config_path}: {e}")
        raise


def validate_config_file(config_file: Union[str, Path]) -> bool:
    """
    Validate a configuration file without loading it.

    Args:
        config_file: Path to configuration file

    Returns:
        True if valid, False otherwise
    """
    try:
        load_config(config_file)
        return True
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False