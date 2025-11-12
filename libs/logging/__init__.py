"""
SynHome Logging Package

Provides simple logging setup with Loguru.
"""

from .setup import setup_logging, get_logger

__all__ = [
    "setup_logging",
    "get_logger",
]