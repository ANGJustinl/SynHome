"""
Simplified Loguru setup for SynHome.

Clean logging configuration without complex formatters.
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger


def setup_logging(
    console_output: bool = True,
    file_path: Optional[str] = None,
    log_level: str = "INFO"
) -> None:
    """
    Setup Loguru logging with simple configuration.

    Args:
        console_output: Whether to output to console
        file_path: Optional log file path
        log_level: Logging level
    """
    # Remove default handler
    logger.remove()

    log_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"

    # Console handler
    if console_output:
        logger.add(
            sys.stderr,
            format=log_format,
            level=log_level,
            colorize=True
        )

    # File handler
    if file_path:
        log_path = Path(file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_path,
            format=log_format,
            level=log_level,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8"
        )

    logger.info("Logging system initialized")


def get_logger(name: str):
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logger.bind(name=name)