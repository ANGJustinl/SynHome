"""
Loguru setup and configuration utilities for SynHome.

Provides centralized logging configuration with support for:
- Console and file output
- Structured logging with JSON format
- Log rotation and retention
- Performance optimization with enqueue
- Custom formatters and filters
"""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from loguru import logger

from ..config.models import LogConfig
from .formatters import JsonFormatter, StructuredFormatter


def setup_logging(
    config: LogConfig,
    extra_handlers: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    Setup Loguru logging based on configuration.

    Args:
        config: Logging configuration
        extra_handlers: Additional handler configurations
    """
    # Remove all existing handlers
    logger.remove()

    # Setup console handler
    if config.console_output:
        setup_console_handler(config)

    # Setup file handler
    if config.file_path:
        setup_file_handler(config)

    # Setup JSON structured file handler if needed
    if config.serialize and config.file_path:
        setup_json_handler(config)

    # Add extra handlers
    if extra_handlers:
        for handler_config in extra_handlers:
            logger.add(**handler_config)

    # Log initialization
    logger.info(
        "Logging system initialized",
        extra={
            "config": {
                "level": config.level,
                "console_output": config.console_output,
                "file_path": config.file_path,
                "serialize": config.serialize,
                "rotation": config.rotation,
                "retention": config.retention,
                "compression": config.compression,
                "enqueue": config.enqueue
            }
        }
    )


def setup_console_handler(config: LogConfig) -> None:
    """Setup console logging handler."""
    console_format = config.format or (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} | {message}"
    )

    logger.add(
        sys.stderr,
        format=console_format,
        level=config.level,
        enqueue=config.enqueue,
        colorize=config.debug and config.environment == "development",
        backtrace=config.debug,
        diagnose=config.debug
    )


def setup_file_handler(config: LogConfig) -> None:
    """Setup file logging handler with rotation."""
    log_path = Path(config.file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_format = config.format or (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line}:{thread} | {message}"
    )

    logger.add(
        log_path,
        format=file_format,
        level=config.level,
        rotation=config.rotation,
        retention=config.retention,
        compression=config.compression,
        enqueue=config.enqueue,
        backtrace=config.debug,
        diagnose=config.debug,
        encoding="utf-8"
    )


def setup_json_handler(config: LogConfig) -> None:
    """Setup JSON structured logging handler."""
    json_path = Path(config.file_path).with_suffix('.jsonl')
    json_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        json_path,
        format="{message}",
        level=config.level,
        rotation=config.rotation,
        retention=config.retention,
        compression=config.compression,
        enqueue=config.enqueue,
        serialize=True,
        encoding="utf-8"
    )


def configure_logger(
    name: str,
    level: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> "logger":
    """
    Configure a named logger with specific settings.

    Args:
        name: Logger name
        level: Log level override
        extra_context: Additional context for all log entries

    Returns:
        Configured logger instance
    """
    log_instance = logger.bind(name=name)

    if level:
        log_instance = log_instance.bind(level=level)

    if extra_context:
        log_instance = log_instance.bind(**extra_context)

    return log_instance


def get_logger(
    name: Optional[str] = None,
    **extra_context
) -> "logger":
    """
    Get a logger instance with optional name and context.

    Args:
        name: Logger name (module name by default)
        **extra_context: Additional context fields

    Returns:
        Logger instance with bound context
    """
    if name:
        log_instance = logger.bind(name=name)
    else:
        log_instance = logger

    if extra_context:
        log_instance = log_instance.bind(**extra_context)

    return log_instance


def create_error_filter(exclude_exceptions: Optional[List[type]] = None) -> callable:
    """
    Create a filter that excludes specific exception types.

    Args:
        exclude_exceptions: List of exception types to exclude

    Returns:
        Filter function
    """
    exclude_exceptions = exclude_exceptions or []

    def error_filter(record):
        """Filter function to exclude specific exceptions."""
        if record["level"].name != "ERROR":
            return True

        if "exception" in record:
            exception = record["exception"]
            for exc_type in exclude_exceptions:
                if isinstance(exception.value, exc_type):
                    return False

        return True

    return error_filter


def create_level_filter(min_level: str, max_level: Optional[str] = None) -> callable:
    """
    Create a filter for log levels within a range.

    Args:
        min_level: Minimum log level
        max_level: Maximum log level (optional)

    Returns:
        Filter function
    """
    level_order = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    try:
        min_idx = level_order.index(min_level.upper())
        max_idx = level_order.index(max_level.upper()) if max_level else len(level_order) - 1
    except ValueError:
        raise ValueError(f"Invalid log level. Must be one of: {level_order}")

    def level_filter(record):
        """Filter function for log level range."""
        current_level = record["level"].name
        try:
            current_idx = level_order.index(current_level)
            return min_idx <= current_idx <= max_idx
        except ValueError:
            return False

    return level_filter


def add_custom_handler(
    sink: Union[str, Path, callable],
    format_string: Optional[str] = None,
    level: str = "INFO",
    **kwargs
) -> int:
    """
    Add a custom logging handler.

    Args:
        sink: Log sink (file path, callable, etc.)
        format_string: Custom format string
        level: Log level
        **kwargs: Additional handler options

    Returns:
        Handler ID
    """
    return logger.add(
        sink,
        format=format_string,
        level=level,
        **kwargs
    )


def remove_handler(handler_id: int) -> None:
    """Remove a logging handler by ID."""
    logger.remove(handler_id)


def get_handler_info() -> List[Dict[str, Any]]:
    """
    Get information about all configured handlers.

    Returns:
        List of handler information dictionaries
    """
    handlers = []

    for handler_id in logger._core.handlers:
        handler = logger._core.handlers[handler_id]
        handlers.append({
            "id": handler_id,
            "sink": str(handler.sink),
            "level": handler.levelname,
            "format": handler.formatter._fmt if hasattr(handler.formatter, '_fmt') else str(handler.formatter),
            "enqueue": handler.enqueue,
            "backtrace": handler.backtrace,
            "diagnose": handler.diagnose
        })

    return handlers


def test_logging_config(config: LogConfig) -> Dict[str, Any]:
    """
    Test logging configuration by writing test entries.

    Args:
        config: Logging configuration to test

    Returns:
        Test results dictionary
    """
    results = {
        "console_output": False,
        "file_output": False,
        "json_output": False,
        "errors": []
    }

    # Setup test logger
    test_logger = logger.bind(test=True)

    try:
        # Test console output
        if config.console_output:
            test_logger.info("Console test message")
            results["console_output"] = True

        # Test file output
        if config.file_path:
            test_log_path = Path(config.file_path).with_suffix('.test.log')
            test_logger.add(
                test_log_path,
                format="{time} | {level} | {message}",
                level="INFO",
                rotation="10 MB",
                retention="1 day"
            )
            test_logger.info("File test message")
            results["file_output"] = test_log_path.exists()

            # Clean up test file
            if test_log_path.exists():
                test_log_path.unlink()

        # Test JSON output
        if config.serialize and config.file_path:
            test_json_path = Path(config.file_path).with_suffix('.test.jsonl')
            test_logger.add(
                test_json_path,
                format="{message}",
                level="INFO",
                serialize=True,
                rotation="10 MB",
                retention="1 day"
            )
            test_logger.info("JSON test message", extra={"test": True})
            results["json_output"] = test_json_path.exists()

            # Clean up test JSON file
            if test_json_path.exists():
                test_json_path.unlink()

    except Exception as e:
        results["errors"].append(str(e))

    return results