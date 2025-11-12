"""
Logging context management for SynHome.

Provides utilities for:
- Contextual logging with automatic scope management
- Request/device/user context tracking
- Performance monitoring context
- Structured log context inheritance
"""

import threading
import time
import uuid
from contextlib import contextmanager
from typing import Dict, Any, Optional, Generator, Union
from collections import defaultdict

import loguru


class LogContext:
    """Thread-local logging context manager."""

    def __init__(self):
        """Initialize log context with thread-local storage."""
        self._local = threading.local()
        self._global_context = {}
        self._context_stack = []

    @property
    def current(self) -> Dict[str, Any]:
        """Get current context dictionary."""
        if not hasattr(self._local, 'context'):
            self._local.context = {}
        return self._local.context

    def set(self, **kwargs) -> None:
        """
        Set context values.

        Args:
            **kwargs: Context key-value pairs
        """
        self.current.update(kwargs)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get context value.

        Args:
            key: Context key
            default: Default value if key not found

        Returns:
            Context value or default
        """
        return self.current.get(key, default)

    def update(self, context: Dict[str, Any]) -> None:
        """
        Update context with dictionary.

        Args:
            context: Context dictionary
        """
        self.current.update(context)

    def clear(self) -> None:
        """Clear current context."""
        self.current.clear()

    def push(self) -> None:
        """Push current context onto stack."""
        self._context_stack.append(self.current.copy())

    def pop(self) -> None:
        """Pop context from stack."""
        if self._context_stack:
            self.current.clear()
            self.current.update(self._context_stack.pop())

    def set_global(self, **kwargs) -> None:
        """
        Set global context values (added to all log entries).

        Args:
            **kwargs: Global context key-value pairs
        """
        self._global_context.update(kwargs)

    def get_global(self) -> Dict[str, Any]:
        """Get global context dictionary."""
        return self._global_context.copy()

    def get_full_context(self) -> Dict[str, Any]:
        """Get combined global and current context."""
        context = self._global_context.copy()
        context.update(self.current)
        return context


# Global log context instance
log_context = LogContext()


@contextmanager
def context_logger(**kwargs) -> Generator[loguru.logger, None, None]:
    """
    Context manager for temporary logging context.

    Args:
        **kwargs: Context values for the duration of the context

    Yields:
        Logger with bound context
    """
    # Push current context
    log_context.push()

    try:
        # Set new context
        log_context.set(**kwargs)

        # Get logger with context
        logger_instance = loguru.logger.bind(**log_context.get_full_context())

        yield logger_instance

    finally:
        # Restore previous context
        log_context.pop()


@contextmanager
def request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs
) -> Generator[loguru.logger, None, None]:
    """
    Context manager for request-based logging.

    Args:
        request_id: Unique request identifier
        user_id: User identifier
        **kwargs: Additional request context

    Yields:
        Logger with request context
    """
    request_id = request_id or str(uuid.uuid4())

    context = {
        "request_id": request_id,
        "timestamp": time.time(),
    }

    if user_id:
        context["user_id"] = user_id

    context.update(kwargs)

    with context_logger(**context) as logger:
        logger.debug("Request started", extra=context)
        try:
            yield logger
        except Exception as e:
            logger.error(f"Request failed: {e}", extra=context)
            raise
        finally:
            logger.debug("Request completed", extra=context)


@contextmanager
def device_context(
    device_id: str,
    device_type: Optional[str] = None,
    **kwargs
) -> Generator[loguru.logger, None, None]:
    """
    Context manager for device-specific logging.

    Args:
        device_id: Device identifier
        device_type: Device type
        **kwargs: Additional device context

    Yields:
        Logger with device context
    """
    context = {
        "device_id": device_id,
        "device_type": device_type,
    }
    context.update(kwargs)

    with context_logger(**context) as logger:
        logger.debug(f"Device operation started: {device_id}")
        try:
            yield logger
        except Exception as e:
            logger.error(f"Device operation failed: {e}")
            raise
        finally:
            logger.debug(f"Device operation completed: {device_id}")


@contextmanager
def performance_context(
    operation: str,
    **kwargs
) -> Generator[loguru.logger, None, None]:
    """
    Context manager for performance monitoring.

    Args:
        operation: Operation name
        **kwargs: Additional performance context

    Yields:
        Logger for performance monitoring
    """
    start_time = time.time()
    operation_id = str(uuid.uuid4())

    context = {
        "operation": operation,
        "operation_id": operation_id,
        "start_time": start_time,
    }
    context.update(kwargs)

    with context_logger(**context) as logger:
        logger.debug(f"Operation started: {operation}")
        try:
            yield logger
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Operation failed after {duration:.3f}s: {e}")
            raise
        finally:
            duration = time.time() - start_time
            logger.debug(f"Operation completed in {duration:.3f}s: {operation}")


@contextmanager
def component_context(
    component: str,
    **kwargs
) -> Generator[loguru.logger, None, None]:
    """
    Context manager for component-specific logging.

    Args:
        component: Component name
        **kwargs: Additional component context

    Yields:
        Logger with component context
    """
    context = {
        "component": component,
    }
    context.update(kwargs)

    with context_logger(**context) as logger:
        logger.debug(f"Component operation: {component}")
        try:
            yield logger
        except Exception as e:
            logger.error(f"Component error in {component}: {e}")
            raise


class ContextTracker:
    """Track and manage logging context across the application."""

    def __init__(self):
        """Initialize context tracker."""
        self._contexts = defaultdict(list)
        self._metrics = defaultdict(int)

    def add_context(self, context_type: str, context: Dict[str, Any]) -> None:
        """
        Add context entry.

        Args:
            context_type: Type of context (request, device, etc.)
            context: Context data
        """
        context["timestamp"] = time.time()
        self._contexts[context_type].append(context)
        self._metrics[f"{context_type}_count"] += 1

    def get_contexts(self, context_type: str, limit: int = 100) -> list:
        """
        Get recent contexts of a specific type.

        Args:
            context_type: Type of context
            limit: Maximum number of contexts to return

        Returns:
            List of context dictionaries
        """
        return self._contexts[context_type][-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get context tracking metrics."""
        return {
            "metrics": dict(self._metrics),
            "active_contexts": {
                context_type: len(contexts)
                for context_type, contexts in self._contexts.items()
            }
        }

    def cleanup_old_contexts(self, max_age: float = 3600.0) -> None:
        """
        Clean up old context entries.

        Args:
            max_age: Maximum age in seconds
        """
        current_time = time.time()

        for context_type, contexts in self._contexts.items():
            # Keep only recent contexts
            self._contexts[context_type] = [
                ctx for ctx in contexts
                if current_time - ctx.get("timestamp", 0) < max_age
            ]


# Global context tracker
context_tracker = ContextTracker()


def get_logger_with_context(**kwargs) -> loguru.logger:
    """
    Get logger with additional context.

    Args:
        **kwargs: Context to bind to logger

    Returns:
        Logger with bound context
    """
    full_context = log_context.get_full_context()
    full_context.update(kwargs)
    return loguru.logger.bind(**full_context)


def log_function_call(func_name: str, args: tuple = (), kwargs: dict = None) -> None:
    """
    Log function call with context.

    Args:
        func_name: Function name
        args: Function arguments
        kwargs: Function keyword arguments
    """
    context = {
        "function": func_name,
        "args_count": len(args),
        "kwargs_keys": list(kwargs.keys()) if kwargs else [],
    }

    logger = get_logger_with_context(**context)
    logger.debug(f"Function called: {func_name}")


def log_api_call(
    method: str,
    endpoint: str,
    status_code: Optional[int] = None,
    duration: Optional[float] = None,
    **kwargs
) -> None:
    """
    Log API call with context.

    Args:
        method: HTTP method
        endpoint: API endpoint
        status_code: Response status code
        duration: Request duration in seconds
        **kwargs: Additional API context
    """
    context = {
        "api_method": method,
        "api_endpoint": endpoint,
        "api_status_code": status_code,
        "api_duration": duration,
    }
    context.update(kwargs)

    logger = get_logger_with_context(**context)

    if status_code and status_code >= 400:
        logger.warning(f"API call failed: {method} {endpoint} -> {status_code}")
    else:
        logger.info(f"API call: {method} {endpoint}")


def set_global_context(**kwargs) -> None:
    """
    Set global logging context.

    Args:
        **kwargs: Global context values
    """
    log_context.set_global(**kwargs)


def get_global_context() -> Dict[str, Any]:
    """Get current global context."""
    return log_context.get_global()


def update_context(**kwargs) -> None:
    """
    Update current logging context.

    Args:
        **kwargs: Context values to update
    """
    log_context.set(**kwargs)


def get_current_context() -> Dict[str, Any]:
    """Get current thread-local context."""
    return log_context.current.copy()