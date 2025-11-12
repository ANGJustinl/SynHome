"""
Startup configuration validation for SynHome.

Provides:
- Application startup validation
- Early error detection and reporting
- Graceful failure handling
- Configuration initialization
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass
import time

import loguru

from .models import AppSettings
from .loader import ConfigLoader, load_config
from .validation_service import (
    ConfigurationValidationService,
    ValidationResult,
    ValidationStatus
)
from .errors import ConfigurationError, ErrorSeverity
from .legacy import is_legacy_config, migrate_config_file


@dataclass
class StartupResult:
    """Result of startup configuration validation."""
    success: bool
    app_settings: Optional[AppSettings]
    validation_result: Optional[ValidationResult]
    startup_time_ms: float
    errors: List[str]
    warnings: List[str]
    critical_failures: List[str]
    recommendations: List[str]


class StartupValidator:
    """Handles configuration validation during application startup."""

    def __init__(
        self,
        config_file: Optional[Union[str, Path]] = None,
        strict_mode: bool = False,
        auto_migrate: bool = True
    ):
        """
        Initialize startup validator.

        Args:
            config_file: Optional configuration file path
            strict_mode: Whether to use strict validation
            auto_migrate: Whether to automatically migrate legacy configs
        """
        self.config_file = config_file
        self.strict_mode = strict_mode
        self.auto_migrate = auto_migrate
        self.validation_service = ConfigurationValidationService()
        self.loader = ConfigLoader()

    def validate_startup_configuration(
        self,
        environment_overrides: Optional[Dict[str, Any]] = None
    ) -> StartupResult:
        """
        Perform complete startup configuration validation.

        Args:
            environment_overrides: Optional environment variable overrides

        Returns:
            StartupResult with validation details
        """
        start_time = time.time()
        loguru.logger.info("Starting configuration validation...")

        errors = []
        warnings = []
        critical_failures = []
        recommendations = []

        try:
            # Step 1: Validate configuration file exists (if specified)
            if self.config_file:
                config_path = Path(self.config_file)
                if not config_path.exists():
                    critical_failures.append(f"Configuration file not found: {config_path}")
                    return self._create_startup_result(
                        success=False,
                        errors=errors,
                        warnings=warnings,
                        critical_failures=critical_failures,
                        recommendations=recommendations,
                        startup_time=start_time
                    )

            # Step 2: Load and validate configuration
            try:
                app_settings = load_config(self.config_file, **(environment_overrides or {}))
                loguru.logger.info("Configuration loaded successfully")
            except Exception as e:
                error_msg = f"Failed to load configuration: {str(e)}"
                critical_failures.append(error_msg)
                loguru.logger.error(error_msg)

                # Try to provide helpful suggestions
                suggestions = self._get_load_error_suggestions(e)
                recommendations.extend(suggestions)

                return self._create_startup_result(
                    success=False,
                    errors=errors,
                    warnings=warnings,
                    critical_failures=critical_failures,
                    recommendations=recommendations,
                    startup_time=start_time
                )

            # Step 3: Validate configuration content
            validation_result = self.validation_service.validate_app_settings(app_settings)

            if not validation_result.is_valid:
                errors.extend(validation_result.errors)
                loguru.logger.error(f"Configuration validation failed: {len(validation_result.errors)} errors")

            if validation_result.warnings:
                warnings.extend(validation_result.warnings)
                loguru.logger.warning(f"Configuration validation warnings: {len(validation_result.warnings)}")

            # Step 4: Perform system-level checks
            system_errors, system_warnings, system_recommendations = self._validate_system_requirements(app_settings)
            errors.extend(system_errors)
            warnings.extend(system_warnings)
            recommendations.extend(system_recommendations)

            # Step 5: Check for critical issues that prevent startup
            critical_errors = [e for e in errors if self._is_critical_error(e)]
            if critical_errors:
                critical_failures.extend(critical_errors)
                loguru.logger.critical(f"Critical configuration errors prevent startup: {len(critical_errors)}")

                return self._create_startup_result(
                    success=False,
                    app_settings=app_settings,
                    validation_result=validation_result,
                    errors=errors,
                    warnings=warnings,
                    critical_failures=critical_failures,
                    recommendations=recommendations,
                    startup_time=start_time
                )

            # Step 6: Generate recommendations based on configuration
            config_recommendations = self._generate_recommendations(app_settings)
            recommendations.extend(config_recommendations)

            startup_time_ms = (time.time() - start_time) * 1000

            loguru.logger.info(f"Startup validation completed successfully in {startup_time_ms:.1f}ms")

            return self._create_startup_result(
                success=True,
                app_settings=app_settings,
                validation_result=validation_result,
                errors=errors,
                warnings=warnings,
                critical_failures=critical_failures,
                recommendations=recommendations,
                startup_time=start_time
            )

        except Exception as e:
            startup_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Unexpected error during startup validation: {str(e)}"
            loguru.logger.exception(error_msg)
            critical_failures.append(error_msg)

            return self._create_startup_result(
                success=False,
                errors=errors,
                warnings=warnings,
                critical_failures=critical_failures,
                recommendations=["Check application logs for detailed error information"],
                startup_time=start_time
            )

    def validate_configuration_file_only(self, config_path: Union[str, Path]) -> StartupResult:
        """
        Validate only the configuration file without loading the full application.

        Args:
            config_path: Path to configuration file

        Returns:
            StartupResult with file validation details
        """
        start_time = time.time()
        loguru.logger.info(f"Validating configuration file: {config_path}")

        errors = []
        warnings = []
        critical_failures = []
        recommendations = []

        config_path = Path(config_path)

        # Check file exists
        if not config_path.exists():
            critical_failures.append(f"Configuration file not found: {config_path}")
            return self._create_startup_result(
                success=False,
                errors=errors,
                warnings=warnings,
                critical_failures=critical_failures,
                recommendations=recommendations,
                startup_time=start_time
            )

        # Check file readability
        if not config_path.is_file():
            critical_failures.append(f"Path is not a file: {config_path}")
            return self._create_startup_result(
                success=False,
                errors=errors,
                warnings=warnings,
                critical_failures=critical_failures,
                recommendations=recommendations,
                startup_time=start_time
            )

        # Validate file format
        try:
            validation_result = self.validation_service.validate_configuration_file(
                config_path,
                strict_mode=self.strict_mode
            )

            if not validation_result.is_valid:
                errors.extend(validation_result.errors)
                critical_failures.extend([e for e in validation_result.errors if self._is_critical_error(e)])

            if validation_result.warnings:
                warnings.extend(validation_result.warnings)

            # Generate file-specific recommendations
            file_recommendations = self._generate_file_recommendations(config_path, validation_result)
            recommendations.extend(file_recommendations)

            startup_time_ms = (time.time() - start_time) * 1000

            success = len(critical_failures) == 0
            if success:
                loguru.logger.info(f"Configuration file validation passed in {startup_time_ms:.1f}ms")
            else:
                loguru.logger.error(f"Configuration file validation failed: {len(critical_failures)} critical errors")

            return self._create_startup_result(
                success=success,
                validation_result=validation_result,
                errors=errors,
                warnings=warnings,
                critical_failures=critical_failures,
                recommendations=recommendations,
                startup_time=start_time
            )

        except Exception as e:
            startup_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Error validating configuration file: {str(e)}"
            loguru.logger.exception(error_msg)
            critical_failures.append(error_msg)

            return self._create_startup_result(
                success=False,
                errors=errors,
                warnings=warnings,
                critical_failures=critical_failures,
                recommendations=recommendations,
                startup_time=start_time
            )

    def check_legacy_configuration(self, config_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """
        Check if configuration file is in legacy format and suggest migration.

        Args:
            config_path: Path to configuration file

        Returns:
            Tuple of (is_legacy, migration_suggestions)
        """
        try:
            config_data = self.loader._load_config_file(Path(config_path))

            if is_legacy_config(config_data):
                suggestions = [
                    "Configuration file is in legacy format",
                    "Consider migrating to the new format for better validation",
                    f"Run: python -m libs.config.legacy.migrate_config_file '{config_path}'"
                ]
                return True, suggestions
            else:
                return False, []

        except Exception:
            return False, []

    def perform_startup_health_check(self, app_settings: AppSettings) -> StartupResult:
        """
        Perform a health check on the loaded configuration.

        Args:
            app_settings: Loaded application settings

        Returns:
            StartupResult with health check details
        """
        start_time = time.time()
        loguru.logger.info("Performing startup health check...")

        errors = []
        warnings = []
        critical_failures = []
        recommendations = []

        # Perform health check
        health_result = self.validation_service.perform_health_check(app_settings)

        if not health_result.is_valid:
            errors.extend(health_result.errors)
            critical_failures.extend([e for e in health_result.errors if self._is_critical_error(e)])

        if health_result.warnings:
            warnings.extend(health_result.warnings)

        # Generate health-specific recommendations
        health_recommendations = self._generate_health_recommendations(app_settings, health_result)
        recommendations.extend(health_recommendations)

        startup_time_ms = (time.time() - start_time) * 1000

        success = len(critical_failures) == 0
        loguru.logger.info(f"Startup health check completed in {startup_time_ms:.1f}ms")

        return self._create_startup_result(
            success=success,
            app_settings=app_settings,
            validation_result=health_result,
            errors=errors,
            warnings=warnings,
            critical_failures=critical_failures,
            recommendations=recommendations,
            startup_time=start_time
        )

    def _validate_system_requirements(
        self,
        app_settings: AppSettings
    ) -> Tuple[List[str], List[str], List[str]]:
        """Validate system-level requirements."""
        errors = []
        warnings = []
        recommendations = []

        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 8):
            errors.append(f"Python {python_version.major}.{python_version.minor} is not supported. Requires Python 3.8+")
        elif python_version < (3, 10):
            warnings.append(f"Consider upgrading to Python 3.10+ for better performance and features")

        # Check required directories
        if app_settings.logging.file_path:
            log_path = Path(app_settings.logging.file_path)
            log_dir = log_path.parent

            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                    recommendations.append(f"Created log directory: {log_dir}")
                except OSError:
                    errors.append(f"Cannot create log directory: {log_dir}")
            elif not os.access(log_dir, os.W_OK):
                errors.append(f"No write permission for log directory: {log_dir}")

        # Check port availability (in development mode)
        if app_settings.debug and app_settings.environment.value == "development":
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex((app_settings.host, app_settings.port))
                sock.close()
                if result == 0:
                    warnings.append(f"Port {app_settings.port} is already in use")
            except Exception:
                pass  # Skip port check if it fails

        # Check environment variables
        if app_settings.zhipuai.enabled and not app_settings.zhipuai.api_key:
            if "ZHIPUAI_API_KEY" in os.environ:
                recommendations.append("ZhipuAI API key is set via environment variable")
            else:
                errors.append("ZhipuAI is enabled but API key is not configured")

        return errors, warnings, recommendations

    def _generate_recommendations(self, app_settings: AppSettings) -> List[str]:
        """Generate recommendations based on configuration."""
        recommendations = []

        # Security recommendations
        if app_settings.debug and app_settings.environment.value == "production":
            recommendations.append("Disable debug mode in production environment")

        if app_settings.host == "0.0.0.0" and app_settings.environment.value == "production":
            recommendations.append("Consider binding to specific interfaces in production")

        # Performance recommendations
        if not app_settings.logging.enqueue:
            recommendations.append("Enable log enqueueing for better performance")

        if app_settings.logging.serialize and app_settings.environment.value == "development":
            recommendations.append("Consider disabling JSON serialization in development for better readability")

        # Reliability recommendations
        if not app_settings.logging.file_path:
            recommendations.append("Consider configuring file logging for persistence")

        if app_settings.zhipuai.enabled and app_settings.zhipuai.max_retries < 3:
            recommendations.append("Consider increasing ZhipuAI max retries for better reliability")

        return recommendations

    def _generate_file_recommendations(
        self,
        config_path: Path,
        validation_result: ValidationResult
    ) -> List[str]:
        """Generate file-specific recommendations."""
        recommendations = []

        # Check file size
        if validation_result.metadata and "file_size" in validation_result.metadata:
            file_size = validation_result.metadata["file_size"]
            if file_size > 1024 * 1024:  # 1MB
                recommendations.append("Consider splitting large configuration files")

        # Check for legacy format
        is_legacy, legacy_suggestions = self.check_legacy_configuration(config_path)
        if is_legacy:
            recommendations.extend(legacy_suggestions)

        return recommendations

    def _generate_health_recommendations(
        self,
        app_settings: AppSettings,
        health_result: ValidationResult
    ) -> List[str]:
        """Generate health check-specific recommendations."""
        recommendations = []

        if health_result.metadata:
            # Check for performance warnings
            if "performance_issues" in health_result.metadata:
                recommendations.append("Consider optimizing configuration for better performance")

            # Check for security warnings
            if "security_warnings" in health_result.metadata:
                recommendations.append("Review security settings in configuration")

        return recommendations

    def _get_load_error_suggestions(self, error: Exception) -> List[str]:
        """Get suggestions for configuration loading errors."""
        error_str = str(error).lower()
        suggestions = []

        if "not found" in error_str:
            suggestions.extend([
                "Check if the configuration file path is correct",
                "Ensure the configuration file exists",
                "Check file permissions"
            ])

        if "permission" in error_str:
            suggestions.extend([
                "Check file and directory permissions",
                "Ensure the application has read access to the configuration file"
            ])

        if "yaml" in error_str or "yml" in error_str:
            suggestions.extend([
                "Check YAML syntax and indentation",
                "Validate YAML structure using an online YAML validator",
                "Ensure proper quoting of special characters"
            ])

        if "json" in error_str:
            suggestions.extend([
                "Check JSON syntax (commas, brackets, quotes)",
                "Validate JSON structure using an online JSON validator"
            ])

        if "validation" in error_str:
            suggestions.extend([
                "Review configuration requirements",
                "Check data types and value ranges",
                "Ensure all required fields are present"
            ])

        return suggestions

    def _is_critical_error(self, error: str) -> bool:
        """Determine if an error is critical (prevents startup)."""
        critical_keywords = [
            "not found",
            "permission denied",
            "invalid format",
            "missing required",
            "port.*out of range",
            "cannot create",
            "no write permission"
        ]

        error_lower = error.lower()
        return any(keyword in error_lower for keyword in critical_keywords)

    def _create_startup_result(
        self,
        success: bool,
        app_settings: Optional[AppSettings] = None,
        validation_result: Optional[ValidationResult] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        critical_failures: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        startup_time: Optional[float] = None
    ) -> StartupResult:
        """Create a StartupResult object."""
        if startup_time is None:
            startup_time = time.time()

        startup_time_ms = (time.time() - startup_time) * 1000

        return StartupResult(
            success=success,
            app_settings=app_settings,
            validation_result=validation_result,
            startup_time_ms=startup_time_ms,
            errors=errors or [],
            warnings=warnings or [],
            critical_failures=critical_failures or [],
            recommendations=recommendations or []
        )


def validate_startup_config(
    config_file: Optional[Union[str, Path]] = None,
    strict_mode: bool = False,
    auto_migrate: bool = True,
    environment_overrides: Optional[Dict[str, Any]] = None
) -> StartupResult:
    """
    Validate configuration during application startup.

    Args:
        config_file: Optional configuration file path
        strict_mode: Whether to use strict validation
        auto_migrate: Whether to automatically migrate legacy configs
        environment_overrides: Optional environment variable overrides

    Returns:
        StartupResult with validation details
    """
    validator = StartupValidator(
        config_file=config_file,
        strict_mode=strict_mode,
        auto_migrate=auto_migrate
    )
    return validator.validate_startup_configuration(environment_overrides)


def validate_config_file_only(
    config_path: Union[str, Path],
    strict_mode: bool = False
) -> StartupResult:
    """
    Validate only the configuration file.

    Args:
        config_path: Path to configuration file
        strict_mode: Whether to use strict validation

    Returns:
        StartupResult with file validation details
    """
    validator = StartupValidator(strict_mode=strict_mode)
    return validator.validate_configuration_file_only(config_path)


def perform_startup_health_check(app_settings: AppSettings) -> StartupResult:
    """
    Perform a health check on the loaded configuration.

    Args:
        app_settings: Loaded application settings

    Returns:
        StartupResult with health check details
    """
    validator = StartupValidator()
    return validator.perform_startup_health_check(app_settings)