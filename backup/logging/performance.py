"""
Performance monitoring utilities for SynHome logging.

Provides:
- Log performance metrics collection
- Throughput and latency monitoring
- Resource usage tracking
- Performance alerting
"""

import time
import threading
import psutil
from collections import defaultdict, deque
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

import loguru


@dataclass
class LogMetrics:
    """Log performance metrics data class."""
    total_entries: int = 0
    entries_per_second: float = 0.0
    average_size_bytes: float = 0.0
    max_size_bytes: int = 0
    min_size_bytes: int = 0
    error_rate: float = 0.0
    buffer_utilization: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    disk_io_mb_per_sec: float = 0.0


@dataclass
class LogEntry:
    """Individual log entry data for tracking."""
    timestamp: float
    level: str
    size_bytes: int
    duration_ms: Optional[float] = None
    component: Optional[str] = None


class PerformanceMonitor:
    """Monitor logging performance in real-time."""

    def __init__(
        self,
        window_size: int = 60,  # seconds
        max_entries: int = 10000,
        alert_thresholds: Optional[Dict[str, float]] = None
    ):
        """
        Initialize performance monitor.

        Args:
            window_size: Time window for metrics calculation (seconds)
            max_entries: Maximum number of entries to keep in memory
            alert_thresholds: Thresholds for performance alerts
        """
        self.window_size = window_size
        self.max_entries = max_entries
        self.alert_thresholds = alert_thresholds or {
            "entries_per_second": 1000.0,
            "error_rate": 0.05,
            "memory_usage_mb": 500.0,
            "cpu_usage_percent": 80.0
        }

        self._entries: deque = deque(maxlen=max_entries)
        self._start_time = time.time()
        self._lock = threading.Lock()
        self._last_metrics = LogMetrics()
        self._alert_callbacks = []

        # Performance history
        self._metrics_history: deque = deque(maxlen=1000)
        self._alerts_history: deque = deque(maxlen=100)

    def record_entry(
        self,
        level: str,
        size_bytes: int,
        duration_ms: Optional[float] = None,
        component: Optional[str] = None
    ) -> None:
        """
        Record a log entry for performance tracking.

        Args:
            level: Log level
            size_bytes: Size of log entry in bytes
            duration_ms: Time taken to process entry
            component: Component that generated the entry
        """
        with self._lock:
            entry = LogEntry(
                timestamp=time.time(),
                level=level,
                size_bytes=size_bytes,
                duration_ms=duration_ms,
                component=component
            )
            self._entries.append(entry)

    def get_metrics(self, window: Optional[int] = None) -> LogMetrics:
        """
        Calculate current performance metrics.

        Args:
            window: Time window for calculation (uses default if None)

        Returns:
            Current performance metrics
        """
        window = window or self.window_size
        current_time = time.time()
        cutoff_time = current_time - window

        with self._lock:
            # Filter entries within time window
            recent_entries = [
                entry for entry in self._entries
                if entry.timestamp >= cutoff_time
            ]

            if not recent_entries:
                return LogMetrics()

            # Calculate basic metrics
            total_entries = len(recent_entries)
            entries_per_second = total_entries / window

            sizes = [entry.size_bytes for entry in recent_entries]
            average_size = sum(sizes) / len(sizes)
            max_size = max(sizes)
            min_size = min(sizes)

            # Calculate error rate
            error_entries = sum(1 for entry in recent_entries if entry.level in ["ERROR", "CRITICAL"])
            error_rate = error_entries / total_entries if total_entries > 0 else 0.0

            # Calculate average processing time
            durations = [entry.duration_ms for entry in recent_entries if entry.duration_ms is not None]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

            # Get system resource usage
            memory_usage = psutil.virtual_memory().used / (1024 * 1024)  # MB
            cpu_usage = psutil.cpu_percent(interval=0.1)
            disk_io = self._get_disk_io_rate()

            metrics = LogMetrics(
                total_entries=total_entries,
                entries_per_second=entries_per_second,
                average_size_bytes=average_size,
                max_size_bytes=max_size,
                min_size_bytes=min_size,
                error_rate=error_rate,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage,
                disk_io_mb_per_sec=disk_io
            )

            self._last_metrics = metrics
            self._metrics_history.append({
                "timestamp": current_time,
                "metrics": asdict(metrics)
            })

            # Check for performance alerts
            self._check_alerts(metrics)

            return metrics

    def _get_disk_io_rate(self) -> float:
        """Calculate disk I/O rate in MB/s."""
        try:
            disk_io = psutil.disk_io_counters()
            if hasattr(self, '_last_disk_io'):
                time_diff = time.time() - self._last_disk_io_time
                if time_diff > 0:
                    bytes_read_diff = disk_io.read_bytes - self._last_disk_io.read_bytes
                    bytes_written_diff = disk_io.write_bytes - self._last_disk_io.write_bytes
                    total_bytes_diff = bytes_read_diff + bytes_written_diff
                    return total_bytes_diff / (1024 * 1024 * time_diff)  # MB/s

            self._last_disk_io = disk_io
            self._last_disk_io_time = time.time()
            return 0.0
        except Exception:
            return 0.0

    def _check_alerts(self, metrics: LogMetrics) -> None:
        """Check for performance alerts and trigger callbacks."""
        alerts = []

        # Check each threshold
        if metrics.entries_per_second > self.alert_thresholds.get("entries_per_second", float('inf')):
            alerts.append({
                "type": "high_throughput",
                "message": f"High log throughput: {metrics.entries_per_second:.1f} entries/sec",
                "value": metrics.entries_per_second,
                "threshold": self.alert_thresholds["entries_per_second"]
            })

        if metrics.error_rate > self.alert_thresholds.get("error_rate", float('inf')):
            alerts.append({
                "type": "high_error_rate",
                "message": f"High error rate: {metrics.error_rate:.1%}",
                "value": metrics.error_rate,
                "threshold": self.alert_thresholds["error_rate"]
            })

        if metrics.memory_usage_mb > self.alert_thresholds.get("memory_usage_mb", float('inf')):
            alerts.append({
                "type": "high_memory",
                "message": f"High memory usage: {metrics.memory_usage_mb:.1f} MB",
                "value": metrics.memory_usage_mb,
                "threshold": self.alert_thresholds["memory_usage_mb"]
            })

        if metrics.cpu_usage_percent > self.alert_thresholds.get("cpu_usage_percent", float('inf')):
            alerts.append({
                "type": "high_cpu",
                "message": f"High CPU usage: {metrics.cpu_usage_percent:.1f}%",
                "value": metrics.cpu_usage_percent,
                "threshold": self.alert_thresholds["cpu_usage_percent"]
            })

        # Trigger alert callbacks
        for alert in alerts:
            self._alerts_history.append({
                "timestamp": time.time(),
                "alert": alert
            })
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception:
                    loguru.logger.exception("Error in alert callback")

    def add_alert_callback(self, callback) -> None:
        """Add callback for performance alerts."""
        self._alert_callbacks.append(callback)

    def get_metrics_history(self, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get metrics history for the specified duration.

        Args:
            duration_minutes: Duration in minutes

        Returns:
            List of historical metrics
        """
        cutoff_time = time.time() - (duration_minutes * 60)
        return [
            entry for entry in self._metrics_history
            if entry["timestamp"] >= cutoff_time
        ]

    def get_alerts_history(self, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get alerts history for the specified duration.

        Args:
            duration_minutes: Duration in minutes

        Returns:
            List of historical alerts
        """
        cutoff_time = time.time() - (duration_minutes * 60)
        return [
            entry for entry in self._alerts_history
            if entry["timestamp"] >= cutoff_time
        ]

    def get_component_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get performance statistics by component."""
        component_stats = defaultdict(lambda: {
            "count": 0,
            "total_size": 0,
            "total_duration": 0,
            "error_count": 0,
            "levels": defaultdict(int)
        })

        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - self.window_size

            for entry in self._entries:
                if entry.timestamp >= cutoff_time and entry.component:
                    stats = component_stats[entry.component]
                    stats["count"] += 1
                    stats["total_size"] += entry.size_bytes
                    stats["levels"][entry.level] += 1

                    if entry.duration_ms:
                        stats["total_duration"] += entry.duration_ms

                    if entry.level in ["ERROR", "CRITICAL"]:
                        stats["error_count"] += 1

        # Calculate derived metrics
        for component, stats in component_stats.items():
            if stats["count"] > 0:
                stats["average_size"] = stats["total_size"] / stats["count"]
                stats["average_duration_ms"] = stats["total_duration"] / stats["count"]
                stats["error_rate"] = stats["error_count"] / stats["count"]
            else:
                stats["average_size"] = 0
                stats["average_duration_ms"] = 0
                stats["error_rate"] = 0

        return dict(component_stats)

    def reset(self) -> None:
        """Reset performance monitor."""
        with self._lock:
            self._entries.clear()
            self._start_time = time.time()
            self._metrics_history.clear()
            self._alerts_history.clear()

    def export_metrics(self, format_type: str = "json") -> str:
        """
        Export current metrics in specified format.

        Args:
            format_type: Export format ('json', 'csv', 'prometheus')

        Returns:
            Formatted metrics string
        """
        metrics = self.get_metrics()

        if format_type == "json":
            import json
            return json.dumps(asdict(metrics), indent=2)

        elif format_type == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(asdict(metrics).keys())
            writer.writerow(asdict(metrics).values())
            return output.getvalue()

        elif format_type == "prometheus":
            lines = [
                f'synhome_log_entries_total {metrics.total_entries}',
                f'synhome_log_entries_per_second {metrics.entries_per_second}',
                f'synhome_log_average_size_bytes {metrics.average_size_bytes}',
                f'synhome_log_error_rate {metrics.error_rate}',
                f'synhome_log_memory_usage_mb {metrics.memory_usage_mb}',
                f'synhome_log_cpu_usage_percent {metrics.cpu_usage_percent}',
                f'synhome_log_disk_io_mb_per_sec {metrics.disk_io_mb_per_sec}',
            ]
            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported format type: {format_type}")


# Global performance monitor instance
_performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return _performance_monitor


def get_log_metrics() -> LogMetrics:
    """Get current log performance metrics."""
    return _performance_monitor.get_metrics()


def record_log_entry(
    level: str,
    message: str,
    component: Optional[str] = None,
    duration_ms: Optional[float] = None
) -> None:
    """
    Record a log entry for performance tracking.

    Args:
        level: Log level
        message: Log message
        component: Component name
        duration_ms: Processing duration
    """
    size_bytes = len(message.encode('utf-8'))
    _performance_monitor.record_entry(level, size_bytes, duration_ms, component)


def start_performance_monitoring() -> None:
    """Start performance monitoring (if not already started)."""
    # Performance monitoring starts automatically when the module is imported
    loguru.logger.info("Performance monitoring started")


def stop_performance_monitoring() -> None:
    """Stop performance monitoring and cleanup."""
    _performance_monitor.reset()
    loguru.logger.info("Performance monitoring stopped")


def get_component_performance(component: str) -> Dict[str, Any]:
    """Get performance statistics for a specific component."""
    stats = _performance_monitor.get_component_stats()
    return stats.get(component, {})


def set_performance_alert_thresholds(**thresholds: float) -> None:
    """Update performance alert thresholds."""
    _performance_monitor.alert_thresholds.update(thresholds)


def add_performance_alert_callback(callback) -> None:
    """Add callback for performance alerts."""
    _performance_monitor.add_alert_callback(callback)


def default_alert_callback(alert: Dict[str, Any]) -> None:
    """Default callback for performance alerts."""
    loguru.logger.warning(
        f"Performance alert: {alert['message']}",
        extra={
            "alert_type": alert["type"],
            "alert_value": alert["value"],
            "alert_threshold": alert["threshold"]
        }
    )


# Register default alert callback
_performance_monitor.add_alert_callback(default_alert_callback)