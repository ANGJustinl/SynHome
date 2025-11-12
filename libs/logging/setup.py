"""
Loguru setup utilities for SynHome.

Provides simple logging configuration.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


def setup_logging(
    log_config: Optional[Dict[str, Any]] = None,
    console_output: bool = True,
    file_path: Optional[str] = None,
    log_level: str = "INFO"
) -> None:
    """
    Setup Loguru logging.

    Args:
        log_config: Logging configuration dictionary
        console_output: Whether to enable console output
        file_path: Optional log file path
        log_level: Log level
    """
    # Remove all existing handlers
    logger.remove()

    # Setup console handler
    if console_output:
        console_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        )
        logger.add(
            sys.stderr,
            format=console_format,
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )

    # Setup file handler
    if file_path:
        log_path = Path(file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        )
        logger.add(
            log_path,
            format=file_format,
            level=log_level,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8"
        )

    logger.info("Logging system initialized")


def get_logger(name: str = "synhome") -> "logger":
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logger.bind(name=name)