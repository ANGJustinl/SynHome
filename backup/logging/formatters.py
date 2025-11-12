"""
Structured logging formatters for SynHome.

Provides custom formatters for:
- JSON structured logging
- Enhanced human-readable formatting
- Context-aware log entries
- Performance-optimized formatting
"""

import json
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path

import loguru


class JsonFormatter:
    """JSON formatter for structured logging with Loguru."""

    def __init__(
        self,
        include_fields: Optional[list] = None,
        exclude_fields: Optional[list] = None,
        pretty_print: bool = False,
        ensure_ascii: bool = False
    ):
        """
        Initialize JSON formatter.

        Args:
            include_fields: List of fields to include (None for all)
            exclude_fields: List of fields to exclude
            pretty_print: Whether to pretty-print JSON
            ensure_ascii: Whether to escape non-ASCII characters
        """
        self.include_fields = include_fields or []
        self.exclude_fields = exclude_fields or []
        self.pretty_print = pretty_print
        self.ensure_ascii = ensure_ascii

    def format_record(self, record: Dict[str, Any]) -> str:
        """
        Format a log record as JSON.

        Args:
            record: Log record dictionary

        Returns:
            JSON string
        """
        # Filter fields
        if self.include_fields:
            filtered_record = {k: v for k, v in record.items() if k in self.include_fields}
        else:
            filtered_record = record.copy()

        # Exclude fields
        for field in self.exclude_fields:
            filtered_record.pop(field, None)

        # Add structured metadata
        structured_record = self._add_metadata(filtered_record)

        # Format as JSON
        if self.pretty_print:
            return json.dumps(structured_record, indent=2, ensure_ascii=self.ensure_ascii, default=str)
        else:
            return json.dumps(structured_record, ensure_ascii=self.ensure_ascii, default=str)

    def _add_metadata(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Add structured metadata to log record."""
        structured = {
            "timestamp": record.get("time", datetime.utcnow().isoformat()),
            "level": record.get("level", {}).get("name", "UNKNOWN"),
            "logger": record.get("name", ""),
            "message": record.get("message", ""),
            "module": record.get("module", ""),
            "function": record.get("function", ""),
            "line": record.get("line", 0),
            "thread": threading.get_ident(),
            "process": record.get("process", {}).get("id", 0),
        }

        # Add exception information if present
        if record.get("exception"):
            structured["exception"] = {
                "type": record["exception"].type,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback
            }

        # Add extra context
        extra_keys = set(record.keys()) - set(structured.keys()) - {"extra"}
        if extra_keys:
            structured["extra"] = {k: record[k] for k in extra_keys}

        # Add user-defined extra fields
        if record.get("extra"):
            structured["context"] = record["extra"]

        return structured


class StructuredFormatter:
    """Enhanced formatter for human-readable structured logging."""

    def __init__(
        self,
        include_timestamp: bool = True,
        include_thread: bool = False,
        include_context: bool = True,
        colorize: bool = True,
        max_width: int = 120
    ):
        """
        Initialize structured formatter.

        Args:
            include_timestamp: Whether to include timestamp
            include_thread: Whether to include thread ID
            include_context: Whether to include extra context
            colorize: Whether to use colors
            max_width: Maximum line width
        """
        self.include_timestamp = include_timestamp
        self.include_thread = include_thread
        self.include_context = include_context
        self.colorize = colorize
        self.max_width = max_width

    def format_record(self, record: Dict[str, Any]) -> str:
        """
        Format a log record for human-readable output.

        Args:
            record: Log record dictionary

        Returns:
            Formatted string
        """
        parts = []

        # Timestamp
        if self.include_timestamp:
            timestamp = record.get("time", datetime.now())
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            parts.append(timestamp_str)

        # Level with color
        level = record.get("level", {}).get("name", "UNKNOWN")
        level_str = f"{level:<8}"
        if self.colorize:
            level_str = self._colorize_level(level, level_str)
        parts.append(level_str)

        # Logger name and location
        name = record.get("name", "")
        function = record.get("function", "")
        line = record.get("line", 0)
        location = f"{name}:{function}:{line}"
        parts.append(location)

        # Thread ID
        if self.include_thread:
            thread_id = threading.get_ident()
            parts.append(f"[{thread_id}]")

        # Message
        message = record.get("message", "")
        parts.append(message)

        # Build main log line
        log_line = " | ".join(parts)

        # Add context information
        context_lines = []
        if self.include_context:
            context_lines = self._format_context(record)

        # Combine main line and context
        if context_lines:
            result = [log_line] + [f"    {line}" for line in context_lines]
            return "\n".join(result)
        else:
            return log_line

    def _colorize_level(self, level: str, level_str: str) -> str:
        """Add color to log level based on severity."""
        colors = {
            "TRACE": "\033[37m",      # White
            "DEBUG": "\033[36m",      # Cyan
            "INFO": "\033[32m",       # Green
            "WARNING": "\033[33m",    # Yellow
            "ERROR": "\033[31m",      # Red
            "CRITICAL": "\033[35m",   # Magenta
        }

        reset = "\033[0m"
        color = colors.get(level, "\033[37m")
        return f"{color}{level_str}{reset}"

    def _format_context(self, record: Dict[str, Any]) -> list:
        """Format extra context information."""
        context_lines = []

        # Exception information
        if record.get("exception"):
            exc = record["exception"]
            context_lines.append(f"Exception: {exc.type}: {exc.value}")

        # Extra context fields
        extra = record.get("extra", {})
        if extra:
            for key, value in extra.items():
                if key not in ["name"]:  # Skip redundant fields
                    if isinstance(value, (dict, list)):
                        value_str = json.dumps(value, ensure_ascii=False, default=str)
                    else:
                        value_str = str(value)
                    context_lines.append(f"{key}: {value_str}")

        return context_lines


class PerformanceFormatter:
    """Performance-optimized formatter for high-throughput logging."""

    def __init__(
        self,
        minimal_format: bool = True,
        buffer_size: int = 1000,
        flush_interval: float = 1.0
    ):
        """
        Initialize performance formatter.

        Args:
            minimal_format: Use minimal log format
            buffer_size: Buffer size for batch processing
            flush_interval: Flush interval in seconds
        """
        self.minimal_format = minimal_format
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer = []
        self.last_flush = time.time()

    def format_record(self, record: Dict[str, Any]) -> str:
        """
        Format a log record with minimal overhead.

        Args:
            record: Log record dictionary

        Returns:
            Formatted string
        """
        if self.minimal_format:
            return self._minimal_format(record)
        else:
            return self._fast_format(record)

    def _minimal_format(self, record: Dict[str, Any]) -> str:
        """Minimal format for maximum performance."""
        timestamp = int(time.time() * 1000)  # Unix timestamp in ms
        level = record.get("level", {}).get("name", "UNKNOWN")[:1]  # First letter
        message = record.get("message", "")
        return f"{timestamp} {level} {message}"

    def _fast_format(self, record: Dict[str, Any]) -> str:
        """Fast format with basic information."""
        timestamp = record.get("time", "").replace(" ", "T")
        level = record.get("level", {}).get("name", "UNKNOWN")
        name = record.get("name", "")
        message = record.get("message", "")
        return f"{timestamp} {level:<8} {name} | {message}"

    def should_flush(self) -> bool:
        """Check if buffer should be flushed."""
        return (
            len(self.buffer) >= self.buffer_size or
            time.time() - self.last_flush >= self.flush_interval
        )

    def add_to_buffer(self, formatted_record: str) -> bool:
        """
        Add formatted record to buffer.

        Args:
            formatted_record: Formatted log record

        Returns:
            True if buffer should be flushed
        """
        self.buffer.append(formatted_record)
        return self.should_flush()

    def flush_buffer(self) -> list:
        """Flush buffer and return all records."""
        records = self.buffer.copy()
        self.buffer.clear()
        self.last_flush = time.time()
        return records


class ContextAwareFormatter:
    """Formatter that automatically adds contextual information."""

    def __init__(
        self,
        default_context: Optional[Dict[str, Any]] = None,
        auto_extract: bool = True
    ):
        """
        Initialize context-aware formatter.

        Args:
            default_context: Default context to add to all records
            auto_extract: Whether to automatically extract context
        """
        self.default_context = default_context or {}
        self.auto_extract = auto_extract

    def format_record(self, record: Dict[str, Any]) -> str:
        """
        Format record with automatic context extraction.

        Args:
            record: Log record dictionary

        Returns:
            Formatted string with context
        """
        # Extract context
        context = self._extract_context(record)

        # Add default context
        context.update(self.default_context)

        # Format with context
        return self._format_with_context(record, context)

    def _extract_context(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract context information from record."""
        context = {}

        # Extract common patterns
        message = record.get("message", "")

        # Device context (e.g., "Device thermostat1: status updated")
        if "device" in message.lower():
            import re
            device_match = re.search(r'device[s]?\s+([^\s:]+)', message, re.IGNORECASE)
            if device_match:
                context["device_id"] = device_match.group(1)

        # User context (e.g., "User admin: action performed")
        if "user" in message.lower():
            import re
            user_match = re.search(r'user\s+([^\s:]+)', message, re.IGNORECASE)
            if user_match:
                context["user_id"] = user_match.group(1)

        # Add extra fields as context
        extra = record.get("extra", {})
        context.update(extra)

        return context

    def _format_with_context(self, record: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Format record with context information."""
        base_message = record.get("message", "")

        if not context:
            return base_message

        # Format context as JSON
        context_str = json.dumps(context, ensure_ascii=False, default=str)

        # Combine message and context
        return f"{base_message} | context: {context_str}"


# Factory functions for common formatter configurations
def create_json_formatter(pretty_print: bool = False) -> JsonFormatter:
    """Create JSON formatter with default settings."""
    return JsonFormatter(
        exclude_fields=["extra", "record"],
        pretty_print=pretty_print,
        ensure_ascii=False
    )


def create_structured_formatter(debug: bool = False) -> StructuredFormatter:
    """Create structured formatter with appropriate settings."""
    return StructuredFormatter(
        include_timestamp=True,
        include_thread=debug,
        include_context=True,
        colorize=debug,
        max_width=120
    )


def create_performance_formatter(high_throughput: bool = True) -> PerformanceFormatter:
    """Create performance-optimized formatter."""
    return PerformanceFormatter(
        minimal_format=high_throughput,
        buffer_size=1000 if high_throughput else 100,
        flush_interval=1.0
    )


def create_context_formatter() -> ContextAwareFormatter:
    """Create context-aware formatter."""
    return ContextAwareFormatter(
        default_context={"service": "synhome"},
        auto_extract=True
    )