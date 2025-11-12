"""
Configuration metrics collection for SynHome.

Provides:
- Configuration validation metrics
- Performance metrics for config operations
- Usage statistics
- Error tracking
- Health metrics aggregation
"""

import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum
import json

from loguru import logger

from .models import AppSettings
from .validation_service import ValidationResult, ValidationStatus
from .errors import ConfigurationError, ErrorSeverity


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """Single metric value with timestamp."""
    value: float
    timestamp: float
    labels: Optional[Dict[str, str]] = None


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    count: int
    sum: float
    min: float
    max: float
    avg: float
    recent_values: List[float]


class ConfigurationMetrics:
    """Collects and manages configuration-related metrics."""

    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector.

        Args:
            max_history: Maximum number of values to keep in history
        """
        self.max_history = max_history
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

        # Initialize default metrics
        self._initialize_default_metrics()

    def _initialize_default_metrics(self):
        """Initialize default configuration metrics."""
        # Configuration loading metrics
        self._counters["config_load_total"] = 0
        self._counters["config_load_success_total"] = 0
        self._counters["config_load_error_total"] = 0

        # Validation metrics
        self._counters["config_validation_total"] = 0
        self._counters["config_validation_success_total"] = 0
        self._counters["config_validation_error_total"] = 0
        self._counters["config_validation_warning_total"] = 0

        # Performance metrics
        self._metrics["config_load_duration_ms"] = deque(maxlen=self.max_history)
        self._metrics["config_validation_duration_ms"] = deque(maxlen=self.max_history)
        self._metrics["health_check_duration_ms"] = deque(maxlen=self.max_history)

        # Error metrics by category
        for category in ["validation", "file_system", "security", "performance"]:
            self._counters[f"errors_{category}_total"] = 0

        # Configuration size metrics
        self._metrics["config_file_size_bytes"] = deque(maxlen=self.max_history)
        self._metrics["config_device_count"] = deque(maxlen=self.max_history)
        self._metrics["config_adapter_count"] = deque(maxlen=self.max_history)

    def record_config_load(self, duration_ms: float, success: bool, file_size: int = 0):
        """
        Record configuration load metrics.

        Args:
            duration_ms: Load duration in milliseconds
            success: Whether load was successful
            file_size: Configuration file size in bytes
        """
        with self._lock:
            self._counters["config_load_total"] += 1
            if success:
                self._counters["config_load_success_total"] += 1
            else:
                self._counters["config_load_error_total"] += 1

            self._metrics["config_load_duration_ms"].append(duration_ms)
            if file_size > 0:
                self._metrics["config_file_size_bytes"].append(file_size)

    def record_config_validation(self, result: ValidationResult):
        """
        Record configuration validation metrics.

        Args:
            result: Validation result to record
        """
        with self._lock:
            self._counters["config_validation_total"] += 1

            if result.is_valid:
                self._counters["config_validation_success_total"] += 1
            else:
                self._counters["config_validation_error_total"] += 1

            if result.warnings:
                self._counters["config_validation_warning_total"] += len(result.warnings)

            self._metrics["config_validation_duration_ms"].append(result.validation_time_ms)

            # Record error counts by category
            for error in result.errors:
                category = self._categorize_error(error)
                self._counters[f"errors_{category}_total"] += 1

    def record_health_check(self, duration_ms: float, status: str):
        """
        Record health check metrics.

        Args:
            duration_ms: Health check duration in milliseconds
            status: Health check status
        """
        with self._lock:
            self._metrics["health_check_duration_ms"].append(duration_ms)
            self._counters[f"health_check_{status}_total"] = self._counters.get(f"health_check_{status}_total", 0) + 1

    def record_config_composition(self, device_count: int, adapter_count: int):
        """
        Record configuration composition metrics.

        Args:
            device_count: Number of devices in configuration
            adapter_count: Number of adapters in configuration
        """
        with self._lock:
            self._metrics["config_device_count"].append(device_count)
            self._metrics["config_adapter_count"].append(adapter_count)

    def record_custom_metric(self, name: str, value: float, metric_type: MetricType = MetricType.GAUGE, labels: Optional[Dict[str, str]] = None):
        """
        Record a custom metric.

        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric
            labels: Optional labels for the metric
        """
        with self._lock:
            if metric_type == MetricType.COUNTER:
                self._counters[name] += int(value)
            elif metric_type == MetricType.GAUGE:
                self._gauges[name] = value
            elif metric_type == MetricType.HISTOGRAM:
                self._metrics[name].append(value)
            elif metric_type == MetricType.TIMER:
                self._timers[name].append(value)

    def get_metric_summary(self, metric_name: str) -> Optional[MetricSummary]:
        """
        Get summary statistics for a metric.

        Args:
            metric_name: Name of the metric

        Returns:
            Metric summary or None if metric not found
        """
        with self._lock:
            if metric_name in self._metrics:
                values = list(self._metrics[metric_name])
                if not values:
                    return None

                return MetricSummary(
                    count=len(values),
                    sum=sum(values),
                    min=min(values),
                    max=max(values),
                    avg=sum(values) / len(values),
                    recent_values=values[-10:]  # Last 10 values
                )
            elif metric_name in self._counters:
                return MetricSummary(
                    count=self._counters[metric_name],
                    sum=float(self._counters[metric_name]),
                    min=float(self._counters[metric_name]),
                    max=float(self._counters[metric_name]),
                    avg=float(self._counters[metric_name]),
                    recent_values=[float(self._counters[metric_name])]
                )
            elif metric_name in self._gauges:
                value = self._gauges[metric_name]
                return MetricSummary(
                    count=1,
                    sum=value,
                    min=value,
                    max=value,
                    avg=value,
                    recent_values=[value]
                )
            else:
                return None

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.

        Returns:
            Dictionary containing all metrics
        """
        with self._lock:
            metrics = {}

            # Counters
            metrics["counters"] = dict(self._counters)

            # Gauges
            metrics["gauges"] = dict(self._gauges)

            # Histogram summaries
            metrics["histograms"] = {}
            for name, values in self._metrics.items():
                if values:
                    values_list = list(values)
                    metrics["histograms"][name] = {
                        "count": len(values_list),
                        "sum": sum(values_list),
                        "min": min(values_list),
                        "max": max(values_list),
                        "avg": sum(values_list) / len(values_list),
                        "recent": values_list[-5:]  # Last 5 values
                    }

            # Timer statistics
            metrics["timers"] = {}
            for name, times in self._timers.items():
                if times:
                    metrics["timers"][name] = {
                        "count": len(times),
                        "sum": sum(times),
                        "min": min(times),
                        "max": max(times),
                        "avg": sum(times) / len(times)
                    }

            return metrics

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance-specific metrics.

        Returns:
            Performance metrics dictionary
        """
        performance_metrics = {}

        # Load performance
        load_summary = self.get_metric_summary("config_load_duration_ms")
        if load_summary:
            performance_metrics["config_load"] = {
                "avg_duration_ms": load_summary.avg,
                "max_duration_ms": load_summary.max,
                "success_rate": self._counters["config_load_success_total"] / max(self._counters["config_load_total"], 1)
            }

        # Validation performance
        validation_summary = self.get_metric_summary("config_validation_duration_ms")
        if validation_summary:
            performance_metrics["config_validation"] = {
                "avg_duration_ms": validation_summary.avg,
                "max_duration_ms": validation_summary.max,
                "success_rate": self._counters["config_validation_success_total"] / max(self._counters["config_validation_total"], 1)
            }

        # Health check performance
        health_summary = self.get_metric_summary("health_check_duration_ms")
        if health_summary:
            performance_metrics["health_check"] = {
                "avg_duration_ms": health_summary.avg,
                "max_duration_ms": health_summary.max
            }

        return performance_metrics

    def get_error_metrics(self) -> Dict[str, Any]:
        """
        Get error-related metrics.

        Returns:
            Error metrics dictionary
        """
        error_metrics = {
            "total_errors": 0,
            "errors_by_category": {}
        }

        # Sum errors by category
        for key, value in self._counters.items():
            if key.startswith("errors_") and key.endswith("_total"):
                category = key[7:-6]  # Extract category name
                error_metrics["errors_by_category"][category] = value
                error_metrics["total_errors"] += value

        # Calculate error rates
        total_operations = self._counters["config_load_total"] + self._counters["config_validation_total"]
        if total_operations > 0:
            error_metrics["error_rate"] = error_metrics["total_errors"] / total_operations
        else:
            error_metrics["error_rate"] = 0.0

        return error_metrics

    def export_prometheus_format(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []

        with self._lock:
            # Export counters
            for name, value in self._counters.items():
                prometheus_name = name.replace("_total", "").replace("-", "_")
                lines.append(f"synhome_config_{prometheus_name}_total {value}")

            # Export gauges
            for name, value in self._gauges.items():
                prometheus_name = name.replace("-", "_")
                lines.append(f"synhome_config_{prometheus_name} {value}")

            # Export histogram summaries
            for name, values in self._metrics.items():
                if values:
                    values_list = list(values)
                    prometheus_name = name.replace("-", "_")
                    lines.append(f"synhome_config_{prometheus_name}_sum {sum(values_list)}")
                    lines.append(f"synhome_config_{prometheus_name}_count {len(values_list)}")

        return "\n".join(lines)

    def export_json_format(self) -> str:
        """
        Export metrics in JSON format.

        Returns:
            JSON-formatted metrics string
        """
        metrics = self.get_all_metrics()
        metrics["export_timestamp"] = time.time()
        return json.dumps(metrics, indent=2)

    def reset_metrics(self):
        """Reset all metrics to initial state."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()
            self._initialize_default_metrics()

    def _categorize_error(self, error: str) -> str:
        """Categorize an error message for metrics."""
        error_lower = error.lower()

        if "validation" in error_lower or "invalid" in error_lower:
            return "validation"
        elif "file" in error_lower or "directory" in error_lower or "permission" in error_lower:
            return "file_system"
        elif "security" in error_lower or "api_key" in error_lower or "authentication" in error_lower:
            return "security"
        elif "performance" in error_lower or "timeout" in error_lower or "slow" in error_lower:
            return "performance"
        else:
            return "other"


class MetricsCollector:
    """High-level metrics collector for configuration operations."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics = ConfigurationMetrics()
        self._start_times: Dict[str, float] = {}

    def start_timer(self, operation: str) -> str:
        """
        Start timing an operation.

        Args:
            operation: Name of the operation

        Returns:
            Timer ID
        """
        timer_id = f"{operation}_{time.time()}"
        self._start_times[timer_id] = time.time()
        return timer_id

    def end_timer(self, timer_id: str, metric_name: Optional[str] = None) -> float:
        """
        End timing an operation and record the duration.

        Args:
            timer_id: Timer ID returned by start_timer
            metric_name: Optional custom metric name

        Returns:
            Duration in milliseconds
        """
        if timer_id not in self._start_times:
            return 0.0

        start_time = self._start_times.pop(timer_id)
        duration_ms = (time.time() - start_time) * 1000

        if metric_name:
            self.metrics.record_custom_metric(metric_name, duration_ms, MetricType.TIMER)

        return duration_ms

    def record_config_load_operation(self, file_path: str, success: bool, duration_ms: float, file_size: int = 0):
        """
        Record a configuration load operation.

        Args:
            file_path: Path to configuration file
            success: Whether operation was successful
            duration_ms: Operation duration
            file_size: File size in bytes
        """
        self.metrics.record_config_load(duration_ms, success, file_size)

        # Record file-specific metrics
        self.metrics.record_custom_metric(
            f"config_load_file_size_bytes",
            file_size,
            MetricType.HISTOGRAM,
            {"file_extension": Path(file_path).suffix}
        )

    def record_validation_operation(self, result: ValidationResult, config_type: str = "unknown"):
        """
        Record a configuration validation operation.

        Args:
            result: Validation result
            config_type: Type of configuration being validated
        """
        self.metrics.record_config_validation(result)

        # Record validation-specific metrics
        labels = {"config_type": config_type}
        self.metrics.record_custom_metric(
            f"validation_error_count",
            len(result.errors),
            MetricType.GAUGE,
            labels
        )
        self.metrics.record_custom_metric(
            f"validation_warning_count",
            len(result.warnings),
            MetricType.GAUGE,
            labels
        )

    def record_health_check_operation(self, status: str, duration_ms: float, checks_performed: int):
        """
        Record a health check operation.

        Args:
            status: Health check status
            duration_ms: Operation duration
            checks_performed: Number of checks performed
        """
        self.metrics.record_health_check(duration_ms, status)
        self.metrics.record_custom_metric(
            "health_check_count",
            checks_performed,
            MetricType.GAUGE
        )

    def record_error(self, error: str, category: str = "unknown", context: Optional[Dict[str, str]] = None):
        """
        Record an error occurrence.

        Args:
            error: Error message
            category: Error category
            context: Additional context
        """
        self.metrics.record_custom_metric(
            f"errors_{category}_total",
            1,
            MetricType.COUNTER,
            context
        )

    def get_metrics_dashboard(self) -> Dict[str, Any]:
        """
        Get metrics formatted for dashboard display.

        Returns:
            Dashboard-ready metrics
        """
        return {
            "performance": self.metrics.get_performance_metrics(),
            "errors": self.metrics.get_error_metrics(),
            "counters": dict(self.metrics._counters),
            "recent_performance": {
                "config_load_ms": list(self.metrics._metrics["config_load_duration_ms"])[-5:],
                "validation_ms": list(self.metrics._metrics["config_validation_duration_ms"])[-5:],
                "health_check_ms": list(self.metrics._metrics["health_check_duration_ms"])[-5:]
            },
            "config_stats": {
                "avg_file_size": sum(self.metrics._metrics["config_file_size_bytes"]) / max(len(self.metrics._metrics["config_file_size_bytes"]), 1),
                "avg_device_count": sum(self.metrics._metrics["config_device_count"]) / max(len(self.metrics._metrics["config_device_count"]), 1),
                "avg_adapter_count": sum(self.metrics._metrics["config_adapter_count"]) / max(len(self.metrics._metrics["config_adapter_count"]), 1)
            }
        }


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_config_load(file_path: str, success: bool, duration_ms: float, file_size: int = 0):
    """Record configuration load metrics."""
    collector = get_metrics_collector()
    collector.record_config_load_operation(file_path, success, duration_ms, file_size)


def record_validation(result: ValidationResult, config_type: str = "unknown"):
    """Record validation metrics."""
    collector = get_metrics_collector()
    collector.record_validation_operation(result, config_type)


def record_health_check(status: str, duration_ms: float, checks_performed: int):
    """Record health check metrics."""
    collector = get_metrics_collector()
    collector.record_health_check_operation(status, duration_ms, checks_performed)


def record_error(error: str, category: str = "unknown", context: Optional[Dict[str, str]] = None):
    """Record error metrics."""
    collector = get_metrics_collector()
    collector.record_error(error, category, context)


def get_metrics_dashboard() -> Dict[str, Any]:
    """Get dashboard-formatted metrics."""
    collector = get_metrics_collector()
    return collector.get_metrics_dashboard()


def export_metrics(format_type: str = "json") -> str:
    """Export metrics in specified format."""
    collector = get_metrics_collector()
    if format_type == "prometheus":
        return collector.metrics.export_prometheus_format()
    elif format_type == "json":
        return collector.metrics.export_json_format()
    else:
        raise ValueError(f"Unsupported export format: {format_type}")