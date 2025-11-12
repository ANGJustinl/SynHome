"""
Configuration health check utilities for SynHome.

Provides:
- Comprehensive health monitoring
- Configuration validation checks
- System resource monitoring
- Health status reporting
- Alerting for configuration issues
"""

import os
import time
import psutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum

import loguru

from .models import AppSettings
from .validation_service import ConfigurationValidationService, ValidationResult, ValidationStatus
from .loader import ConfigLoader
from .errors import ConfigurationError, ErrorSeverity


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    timestamp: Optional[str] = None


@dataclass
class SystemHealthReport:
    """Comprehensive system health report."""
    overall_status: HealthStatus
    checks: List[HealthCheckResult]
    summary: Dict[str, Any]
    timestamp: str
    total_duration_ms: float
    recommendations: List[str]


class ConfigurationHealthChecker:
    """Performs comprehensive health checks on configuration and system."""

    def __init__(self):
        """Initialize health checker."""
        self.validation_service = ConfigurationValidationService()
        self.check_history: List[SystemHealthReport] = []
        self.max_history_size = 50

    def perform_full_health_check(self, app_settings: AppSettings) -> SystemHealthReport:
        """
        Perform comprehensive health check.

        Args:
            app_settings: Application settings to check

        Returns:
            Complete health report
        """
        start_time = time.time()
        logger = loguru.logger.bind(component="health_checker")

        logger.info("Starting comprehensive health check...")
        checks = []

        # 1. Configuration validation check
        config_check = self._check_configuration_validation(app_settings)
        checks.append(config_check)

        # 2. File system check
        fs_check = self._check_file_system(app_settings)
        checks.append(fs_check)

        # 3. System resources check
        resources_check = self._check_system_resources()
        checks.append(resources_check)

        # 4. Security check
        security_check = self._check_security_configuration(app_settings)
        checks.append(security_check)

        # 5. Performance check
        performance_check = self._check_performance_configuration(app_settings)
        checks.append(performance_check)

        # 6. Dependencies check
        dependencies_check = self._check_dependencies(app_settings)
        checks.append(dependencies_check)

        # Determine overall status
        overall_status = self._determine_overall_status(checks)

        # Generate summary
        summary = self._generate_health_summary(checks)

        # Generate recommendations
        recommendations = self._generate_health_recommendations(checks)

        total_duration_ms = (time.time() - start_time) * 1000

        report = SystemHealthReport(
            overall_status=overall_status,
            checks=checks,
            summary=summary,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            total_duration_ms=total_duration_ms,
            recommendations=recommendations
        )

        # Store in history
        self._store_health_report(report)

        logger.info(f"Health check completed: {overall_status.value} ({total_duration_ms:.1f}ms)")

        return report

    def perform_quick_health_check(self, app_settings: AppSettings) -> HealthCheckResult:
        """
        Perform quick health check (essential checks only).

        Args:
            app_settings: Application settings to check

        Returns:
            Quick health check result
        """
        start_time = time.time()

        # Perform essential checks
        config_check = self._check_configuration_validation(app_settings)
        fs_check = self._check_file_system(app_settings)

        # Determine status based on critical checks
        if config_check.status == HealthStatus.UNHEALTHY or fs_check.status == HealthStatus.UNHEALTHY:
            overall_status = HealthStatus.UNHEALTHY
        elif config_check.status == HealthStatus.WARNING or fs_check.status == HealthStatus.WARNING:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.HEALTHY

        duration_ms = (time.time() - start_time) * 1000

        return HealthCheckResult(
            name="quick_health_check",
            status=overall_status,
            message=f"Quick health check: {overall_status.value}",
            details={
                "configuration": config_check.status.value,
                "file_system": fs_check.status.value
            },
            duration_ms=duration_ms,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    def check_specific_component(
        self,
        component: str,
        app_settings: AppSettings
    ) -> HealthCheckResult:
        """
        Check health of a specific component.

        Args:
            component: Component name to check
            app_settings: Application settings

        Returns:
            Component-specific health check result
        """
        start_time = time.time()

        if component == "configuration":
            return self._check_configuration_validation(app_settings)
        elif component == "file_system":
            return self._check_file_system(app_settings)
        elif component == "system_resources":
            return self._check_system_resources()
        elif component == "security":
            return self._check_security_configuration(app_settings)
        elif component == "performance":
            return self._check_performance_configuration(app_settings)
        elif component == "dependencies":
            return self._check_dependencies(app_settings)
        else:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=component,
                status=HealthStatus.WARNING,
                message=f"Unknown component: {component}",
                duration_ms=duration_ms,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
            )

    def get_health_history(self, limit: int = 10) -> List[SystemHealthReport]:
        """Get recent health check history."""
        return self.check_history[-limit:] if limit > 0 else self.check_history

    def _check_configuration_validation(self, app_settings: AppSettings) -> HealthCheckResult:
        """Check configuration validation."""
        start_time = time.time()

        try:
            validation_result = self.validation_service.perform_health_check(app_settings)

            if validation_result.is_valid:
                status = HealthStatus.HEALTHY
                message = "Configuration validation passed"
            else:
                critical_errors = [e for e in validation_result.errors if self._is_critical_error(e)]
                if critical_errors:
                    status = HealthStatus.UNHEALTHY
                    message = f"Configuration validation failed: {len(critical_errors)} critical errors"
                else:
                    status = HealthStatus.WARNING
                    message = f"Configuration validation warnings: {len(validation_result.warnings)} warnings"

            return HealthCheckResult(
                name="configuration_validation",
                status=status,
                message=message,
                details={
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "validation_time_ms": validation_result.validation_time_ms
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
            )

        except Exception as e:
            return HealthCheckResult(
                name="configuration_validation",
                status=HealthStatus.UNHEALTHY,
                message=f"Configuration validation error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
            )

    def _check_file_system(self, app_settings: AppSettings) -> HealthCheckResult:
        """Check file system health."""
        start_time = time.time()
        issues = []

        # Check log directory
        if app_settings.logging.file_path:
            log_path = Path(app_settings.logging.file_path)
            log_dir = log_path.parent

            if not log_dir.exists():
                issues.append(f"Log directory does not exist: {log_dir}")
            elif not os.access(log_dir, os.W_OK):
                issues.append(f"No write permission for log directory: {log_dir}")
            else:
                # Check disk space
                try:
                    stat = psutil.disk_usage(log_dir)
                    free_percent = (stat.free / stat.total) * 100
                    if free_percent < 5:
                        issues.append(f"Low disk space: {free_percent:.1f}% free")
                    elif free_percent < 10:
                        issues.append(f"Disk space getting low: {free_percent:.1f}% free")
                except Exception:
                    issues.append("Unable to check disk space")

        # Check configuration directory
        config_dir = Path("config")
        if not config_dir.exists():
            issues.append("Configuration directory does not exist")
        elif not os.access(config_dir, os.R_OK):
            issues.append("No read permission for configuration directory")

        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "File system checks passed"
        elif any("does not exist" in issue or "permission" in issue for issue in issues):
            status = HealthStatus.UNHEALTHY
            message = f"File system issues: {len(issues)} problems"
        else:
            status = HealthStatus.WARNING
            message = f"File system warnings: {len(issues)} warnings"

        return HealthCheckResult(
            name="file_system",
            status=status,
            message=message,
            details={
                "issues": issues,
                "log_path": str(app_settings.logging.file_path) if app_settings.logging.file_path else None
            },
            duration_ms=(time.time() - start_time) * 1000,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    def _check_system_resources(self) -> HealthCheckResult:
        """Check system resource utilization."""
        start_time = time.time()
        issues = []

        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            elif cpu_percent > 70:
                issues.append(f"Elevated CPU usage: {cpu_percent:.1f}%")

            # Check memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            if memory_percent > 90:
                issues.append(f"High memory usage: {memory_percent:.1f}%")
            elif memory_percent > 80:
                issues.append(f"Elevated memory usage: {memory_percent:.1f}%")

            # Check disk usage for current directory
            disk = psutil.disk_usage('.')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > 90:
                issues.append(f"High disk usage: {disk_percent:.1f}%")
            elif disk_percent > 80:
                issues.append(f"Elevated disk usage: {disk_percent:.1f}%")

            # Check load average (Unix-like systems)
            if hasattr(os, 'getloadavg'):
                load1, load5, load15 = os.getloadavg()
                cpu_count = psutil.cpu_count()
                if load1 > cpu_count * 2:
                    issues.append(f"High system load: {load1:.2f} (CPU count: {cpu_count})")

        except Exception as e:
            issues.append(f"Error checking system resources: {str(e)}")

        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "System resources are healthy"
        elif any("High" in issue for issue in issues):
            status = HealthStatus.WARNING
            message = f"System resource warnings: {len(issues)} issues"
        else:
            status = HealthStatus.HEALTHY
            message = f"System resource monitoring: {len(issues)} observations"

        return HealthCheckResult(
            name="system_resources",
            status=status,
            message=message,
            details={
                "issues": issues,
                "cpu_percent": cpu_percent if 'cpu_percent' in locals() else None,
                "memory_percent": memory_percent if 'memory_percent' in locals() else None,
                "disk_percent": disk_percent if 'disk_percent' in locals() else None
            },
            duration_ms=(time.time() - start_time) * 1000,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    def _check_security_configuration(self, app_settings: AppSettings) -> HealthCheckResult:
        """Check security-related configuration."""
        start_time = time.time()
        warnings = []

        # Check debug mode in production
        if app_settings.debug and app_settings.environment.value == "production":
            warnings.append("Debug mode enabled in production environment")

        # Check host binding
        if app_settings.host == "0.0.0.0" and app_settings.environment.value == "production":
            warnings.append("Binding to all interfaces (0.0.0.0) in production")

        # Check ZhipuAI configuration
        if app_settings.zhipuai.enabled:
            if not app_settings.zhipuai.api_key:
                warnings.append("ZhipuAI enabled but API key not configured")
            elif len(app_settings.zhipuai.api_key) < 20:
                warnings.append("ZhipuAI API key appears to be too short")

        # Check for insecure defaults
        if app_settings.port < 1024 and app_settings.environment.value == "production":
            warnings.append(f"Using privileged port {app_settings.port} in production")

        # Determine status
        if not warnings:
            status = HealthStatus.HEALTHY
            message = "Security configuration is acceptable"
        else:
            status = HealthStatus.WARNING
            message = f"Security warnings: {len(warnings)} issues"

        return HealthCheckResult(
            name="security",
            status=status,
            message=message,
            details={
                "warnings": warnings,
                "environment": app_settings.environment.value,
                "debug_enabled": app_settings.debug,
                "zhipuai_enabled": app_settings.zhipuai.enabled
            },
            duration_ms=(time.time() - start_time) * 1000,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    def _check_performance_configuration(self, app_settings: AppSettings) -> HealthCheckResult:
        """Check performance-related configuration."""
        start_time = time.time()
        warnings = []

        # Check logging configuration
        if not app_settings.logging.enqueue:
            warnings.append("Log enqueueing disabled - may impact performance")

        if app_settings.logging.serialize and app_settings.environment.value == "development":
            warnings.append("JSON serialization enabled in development - may impact readability")

        # Check hot reload in production
        if app_settings.hot_reload.enabled and app_settings.environment.value == "production":
            warnings.append("Hot reload enabled in production - may impact performance")

        # Check ZhipuAI timeout
        if app_settings.zhipuai.enabled and app_settings.zhipuai.timeout > 60:
            warnings.append("ZhipuAI timeout is high - may cause slow responses")

        # Determine status
        if not warnings:
            status = HealthStatus.HEALTHY
            message = "Performance configuration is optimized"
        else:
            status = HealthStatus.WARNING
            message = f"Performance warnings: {len(warnings)} issues"

        return HealthCheckResult(
            name="performance",
            status=status,
            message=message,
            details={
                "warnings": warnings,
                "log_enqueueing": app_settings.logging.enqueue,
                "log_serialization": app_settings.logging.serialize,
                "hot_reload_enabled": app_settings.hot_reload.enabled
            },
            duration_ms=(time.time() - start_time) * 1000,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    def _check_dependencies(self, app_settings: AppSettings) -> HealthCheckResult:
        """Check external dependencies."""
        start_time = time.time()
        issues = []

        # Check ZhipuAI connectivity if enabled
        if app_settings.zhipuai.enabled and app_settings.zhipuai.api_key:
            try:
                # This would be a basic connectivity test
                # For now, just check if API key format looks reasonable
                if len(app_settings.zhipuai.api_key) < 10:
                    issues.append("ZhipuAI API key appears invalid")
            except Exception as e:
                issues.append(f"ZhipuAI connectivity check failed: {str(e)}")

        # Check for required Python packages
        try:
            import yaml
            import psutil
        except ImportError as e:
            issues.append(f"Missing required package: {str(e)}")

        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "All dependencies are available"
        else:
            status = HealthStatus.WARNING
            message = f"Dependency issues: {len(issues)} problems"

        return HealthCheckResult(
            name="dependencies",
            status=status,
            message=message,
            details={
                "issues": issues,
                "zhipuai_enabled": app_settings.zhipuai.enabled
            },
            duration_ms=(time.time() - start_time) * 1000,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    def _determine_overall_status(self, checks: List[HealthCheckResult]) -> HealthStatus:
        """Determine overall health status from individual checks."""
        if any(check.status == HealthStatus.UNHEALTHY for check in checks):
            return HealthStatus.UNHEALTHY
        elif any(check.status == HealthStatus.DEGRADED for check in checks):
            return HealthStatus.DEGRADED
        elif any(check.status == HealthStatus.WARNING for check in checks):
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY

    def _generate_health_summary(self, checks: List[HealthCheckResult]) -> Dict[str, Any]:
        """Generate health summary statistics."""
        status_counts = {}
        for status in HealthStatus:
            status_counts[status.value] = sum(1 for check in checks if check.status == status)

        total_issues = sum(len(check.details.get('issues', [])) if check.details else 0 for check in checks)
        total_warnings = sum(len(check.details.get('warnings', [])) if check.details else 0 for check in checks)

        return {
            "total_checks": len(checks),
            "status_counts": status_counts,
            "total_issues": total_issues,
            "total_warnings": total_warnings,
            "checks_performed": [check.name for check in checks]
        }

    def _generate_health_recommendations(self, checks: List[HealthCheckResult]) -> List[str]:
        """Generate health improvement recommendations."""
        recommendations = []

        for check in checks:
            if check.status in [HealthStatus.WARNING, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]:
                if check.name == "file_system":
                    recommendations.extend([
                        "Ensure log directory exists and has write permissions",
                        "Monitor disk space usage",
                        "Check configuration file accessibility"
                    ])
                elif check.name == "security":
                    recommendations.extend([
                        "Disable debug mode in production",
                        "Use specific host binding instead of 0.0.0.0 in production",
                        "Review API key security practices"
                    ])
                elif check.name == "performance":
                    recommendations.extend([
                        "Enable log enqueueing for better performance",
                        "Review hot reload settings for production",
                        "Optimize logging configuration"
                    ])
                elif check.name == "system_resources":
                    recommendations.extend([
                        "Monitor system resource usage",
                        "Consider scaling resources if consistently high",
                        "Investigate high CPU or memory usage patterns"
                    ])

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)

        return unique_recommendations

    def _is_critical_error(self, error: str) -> bool:
        """Determine if an error is critical."""
        critical_keywords = [
            "not found",
            "permission denied",
            "cannot create",
            "no write permission",
            "invalid format"
        ]
        return any(keyword in error.lower() for keyword in critical_keywords)

    def _store_health_report(self, report: SystemHealthReport) -> None:
        """Store health report in history."""
        self.check_history.append(report)

        # Keep only recent reports
        if len(self.check_history) > self.max_history_size:
            self.check_history = self.check_history[-self.max_history_size:]


# Global health checker instance
_health_checker: Optional[ConfigurationHealthChecker] = None


def get_health_checker() -> ConfigurationHealthChecker:
    """Get or create the global health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = ConfigurationHealthChecker()
    return _health_checker


def perform_full_health_check(app_settings: AppSettings) -> SystemHealthReport:
    """Perform comprehensive health check."""
    checker = get_health_checker()
    return checker.perform_full_health_check(app_settings)


def perform_quick_health_check(app_settings: AppSettings) -> HealthCheckResult:
    """Perform quick health check."""
    checker = get_health_checker()
    return checker.perform_quick_health_check(app_settings)


def check_component_health(component: str, app_settings: AppSettings) -> HealthCheckResult:
    """Check health of a specific component."""
    checker = get_health_checker()
    return checker.check_specific_component(component, app_settings)


def get_health_history(limit: int = 10) -> List[SystemHealthReport]:
    """Get health check history."""
    checker = get_health_checker()
    return checker.get_health_history(limit)