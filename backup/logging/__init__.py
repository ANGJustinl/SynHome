"""
SynHome Logging Package

Provides structured logging with Loguru, including:
- Loguru wrapper and setup utilities
- Structured logging with context
- Performance monitoring
- Log rotation and retention management
"""

from .setup import setup_logging, configure_logger, get_logger
from .formatters import JsonFormatter, StructuredFormatter
from .context import LogContext, log_context
from .performance import LogMetrics, get_log_metrics

__all__ = [
    "setup_logging",
    "configure_logger",
    "get_logger",
    "JsonFormatter",
    "StructuredFormatter",
    "LogContext",
    "log_context",
    "LogMetrics",
    "get_log_metrics",
]

__version__ = "1.0.0"