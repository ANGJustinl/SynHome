"""
Configuration validation service for SynHome.

Provides comprehensive validation services:
- Configuration file validation
- Runtime configuration validation
- Validation error reporting
- Configuration health checks
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import time

from loguru import logger

from .models import AppSettings
from .validator import ConfigValidator, ConfigValidationError
from .devices import DeviceConfig, AdapterConfig
from .loader import ConfigLoader


class ValidationStatus(Enum):
    """Configuration validation status."""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    status: ValidationStatus
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validation_time_ms: float
    config_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ValidationReport:
    """Comprehensive validation report."""
    overall_status: ValidationStatus
    results: List[ValidationResult]
    total_errors: int
    total_warnings: int
    validation_time_ms: float
    timestamp: str
    config_summary: Dict[str, Any]


class ConfigurationValidationService:
    """Service for comprehensive configuration validation."""

    def __init__(self):
        """Initialize validation service."""
        self.validator = ConfigValidator()
        self.loader = ConfigLoader()
        self.validation_history: List[ValidationReport] = []
        self.max_history_size = 100

    def validate_configuration_file(
        self,
        config_path: Union[str, Path],
        strict_mode: bool = False
    ) -> ValidationResult:
        """
        Validate a configuration file.

        Args:
            config_path: Path to configuration file
            strict_mode: Whether to use strict validation

        Returns:
            ValidationResult with validation details
        """
        start_time = time.time()
        config_path = Path(config_path)

        logger.info(f"Validating configuration file: {config_path}")

        try:
            # Load configuration
            config_data = self.loader._load_config_file(config_path)

            # Validate basic structure and Pydantic model
            is_valid, errors, warnings = self.validator.validate_config_file(str(config_path))

            # Additional validation in strict mode
            if strict_mode and is_valid:
                strict_errors, strict_warnings = self._strict_validation(config_data)
                errors.extend(strict_errors)
                warnings.extend(strict_warnings)

            validation_time_ms = (time.time() - start_time) * 1000

            # Determine status
            if not is_valid:
                status = ValidationStatus.INVALID
            elif errors:
                status = ValidationStatus.ERROR
            elif warnings:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID

            result = ValidationResult(
                status=status,
                is_valid=is_valid and len(errors) == 0,
                errors=errors,
                warnings=warnings,
                validation_time_ms=validation_time_ms,
                config_path=str(config_path),
                metadata={
                    "file_size": config_path.stat().st_size if config_path.exists() else 0,
                    "strict_mode": strict_mode,
                    "config_keys": list(config_data.keys()) if config_data else []
                }
            )

            logger.info(f"Configuration validation completed: {status.value} "
                       f"({len(errors)} errors, {len(warnings)} warnings, "
                       f"{validation_time_ms:.1f}ms)")

            return result

        except Exception as e:
            validation_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Validation failed: {str(e)}"
            logger.error(error_msg)

            return ValidationResult(
                status=ValidationStatus.ERROR,
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                validation_time_ms=validation_time_ms,
                config_path=str(config_path)
            )

    def validate_configuration_data(
        self,
        config_data: Dict[str, Any],
        config_name: str = "inline_config"
    ) -> ValidationResult:
        """
        Validate configuration data directly.

        Args:
            config_data: Configuration dictionary
            config_name: Name for identification

        Returns:
            ValidationResult with validation details
        """
        start_time = time.time()

        logger.info(f"Validating configuration data: {config_name}")

        try:
            # Validate with Pydantic model
            app_settings = AppSettings(**config_data)

            # Validate with environment validator
            is_valid, errors, warnings = self.validator.validate_environment_config(app_settings)

            # Additional checks
            additional_errors, additional_warnings = self._additional_validation(config_data)
            errors.extend(additional_errors)
            warnings.extend(additional_warnings)

            validation_time_ms = (time.time() - start_time) * 1000

            # Determine status
            if not is_valid:
                status = ValidationStatus.INVALID
            elif errors:
                status = ValidationStatus.ERROR
            elif warnings:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID

            result = ValidationResult(
                status=status,
                is_valid=is_valid and len(errors) == 0,
                errors=errors,
                warnings=warnings,
                validation_time_ms=validation_time_ms,
                config_path=config_name,
                metadata={
                    "config_keys": list(config_data.keys()),
                    "environment": config_data.get("environment", "unknown")
                }
            )

            logger.info(f"Configuration data validation completed: {status.value} "
                       f"({len(errors)} errors, {len(warnings)} warnings)")

            return result

        except Exception as e:
            validation_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Configuration validation failed: {str(e)}"
            logger.error(error_msg)

            return ValidationResult(
                status=ValidationStatus.ERROR,
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                validation_time_ms=validation_time_ms,
                config_path=config_name
            )

    def validate_app_settings(self, app_settings: AppSettings) -> ValidationResult:
        """
        Validate an AppSettings instance.

        Args:
            app_settings: AppSettings instance to validate

        Returns:
            ValidationResult with validation details
        """
        start_time = time.time()

        logger.info("Validating AppSettings instance")

        try:
            # Validate with environment validator
            is_valid, errors, warnings = self.validator.validate_environment_config(app_settings)

            # Additional runtime checks
            runtime_errors, runtime_warnings = self._runtime_validation(app_settings)
            errors.extend(runtime_errors)
            warnings.extend(runtime_warnings)

            validation_time_ms = (time.time() - start_time) * 1000

            # Determine status
            if not is_valid:
                status = ValidationStatus.INVALID
            elif errors:
                status = ValidationStatus.ERROR
            elif warnings:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID

            result = ValidationResult(
                status=status,
                is_valid=is_valid and len(errors) == 0,
                errors=errors,
                warnings=warnings,
                validation_time_ms=validation_time_ms,
                metadata={
                    "environment": app_settings.environment.value,
                    "debug": app_settings.debug,
                    "host": app_settings.host,
                    "port": app_settings.port
                }
            )

            logger.info(f"AppSettings validation completed: {status.value}")

            return result

        except Exception as e:
            validation_time_ms = (time.time() - start_time) * 1000
            error_msg = f"AppSettings validation failed: {str(e)}"
            logger.error(error_msg)

            return ValidationResult(
                status=ValidationStatus.ERROR,
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                validation_time_ms=validation_time_ms
            )

    def validate_multiple_configurations(
        self,
        config_paths: List[Union[str, Path]]
    ) -> ValidationReport:
        """
        Validate multiple configuration files.

        Args:
            config_paths: List of configuration file paths

        Returns:
            Comprehensive validation report
        """
        start_time = time.time()
        logger.info(f"Validating {len(config_paths)} configuration files")

        results = []
        total_errors = 0
        total_warnings = 0

        for config_path in config_paths:
            result = self.validate_configuration_file(config_path)
            results.append(result)
            total_errors += len(result.errors)
            total_warnings += len(result.warnings)

        validation_time_ms = (time.time() - start_time) * 1000

        # Determine overall status
        if total_errors > 0:
            overall_status = ValidationStatus.ERROR
        elif total_warnings > 0:
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.VALID

        report = ValidationReport(
            overall_status=overall_status,
            results=results,
            total_errors=total_errors,
            total_warnings=total_warnings,
            validation_time_ms=validation_time_ms,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            config_summary={
                "total_files": len(config_paths),
                "valid_files": sum(1 for r in results if r.is_valid),
                "invalid_files": sum(1 for r in results if not r.is_valid),
                "files_with_warnings": sum(1 for r in results if r.warnings)
            }
        )

        # Store in history
        self._store_validation_report(report)

        logger.info(f"Multiple configuration validation completed: {overall_status.value} "
                   f"({total_errors} errors, {total_warnings} warnings)")

        return report

    def perform_health_check(self, app_settings: AppSettings) -> ValidationResult:
        """
        Perform a health check on current configuration.

        Args:
            app_settings: Current application settings

        Returns:
            ValidationResult with health check details
        """
        start_time = time.time()
        logger.info("Performing configuration health check")

        errors = []
        warnings = []

        # Check critical settings
        if app_settings.port < 1024 and app_settings.environment.value == "production":
            warnings.append("Using privileged port (< 1024) in production")

        if app_settings.debug and app_settings.environment.value == "production":
            warnings.append("Debug mode is enabled in production environment")

        # Check logging configuration
        if app_settings.logging.file_path:
            log_path = Path(app_settings.logging.file_path)
            if not log_path.parent.exists():
                errors.append(f"Log directory does not exist: {log_path.parent}")
            elif not self._check_write_permission(log_path.parent):
                errors.append(f"No write permission for log directory: {log_path.parent}")

        # Check ZhipuAI configuration
        if app_settings.zhipuai.enabled:
            if not app_settings.zhipuai.api_key:
                errors.append("ZhipuAI is enabled but API key is not configured")
            elif len(app_settings.zhipuai.api_key) < 10:
                errors.append("ZhipuAI API key appears to be invalid (too short)")

        # Check device and adapter configurations
        if hasattr(app_settings, 'devices'):
            device_ids = [d.id for d in app_settings.devices]
            if len(device_ids) != len(set(device_ids)):
                errors.append("Duplicate device IDs found in configuration")

        if hasattr(app_settings, 'adapters'):
            adapter_ids = [a.id for a in app_settings.adapters]
            if len(adapter_ids) != len(set(adapter_ids)):
                errors.append("Duplicate adapter IDs found in configuration")

        validation_time_ms = (time.time() - start_time) * 1000

        # Determine status
        if errors:
            status = ValidationStatus.ERROR
        elif warnings:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID

        result = ValidationResult(
            status=status,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validation_time_ms=validation_time_ms,
            metadata={
                "health_check": True,
                "environment": app_settings.environment.value,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        )

        logger.info(f"Configuration health check completed: {status.value}")

        return result

    def get_validation_history(self, limit: int = 10) -> List[ValidationReport]:
        """
        Get recent validation history.

        Args:
            limit: Maximum number of reports to return

        Returns:
            List of recent validation reports
        """
        return self.validation_history[-limit:] if limit > 0 else self.validation_history

    def export_validation_report(
        self,
        report: ValidationReport,
        output_path: Union[str, Path],
        format_type: str = "json"
    ) -> None:
        """
        Export validation report to file.

        Args:
            report: Validation report to export
            output_path: Output file path
            format_type: Export format ('json' or 'yaml')
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to serializable format
        report_data = asdict(report)
        report_data["overall_status"] = report.overall_status.value

        # Convert validation results
        for i, result in enumerate(report_data["results"]):
            result["status"] = report.results[i].status.value

        if format_type.lower() == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
        elif format_type.lower() == "yaml":
            import yaml
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(report_data, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

        logger.info(f"Validation report exported to: {output_path}")

    def _strict_validation(self, config_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Perform strict validation checks."""
        errors = []
        warnings = []

        # Check for required sections
        required_sections = ["environment", "debug", "host", "port", "logging"]
        for section in required_sections:
            if section not in config_data:
                errors.append(f"Missing required configuration section: {section}")

        # Check data types strictly
        if "port" in config_data and not isinstance(config_data["port"], int):
            errors.append("Port must be an integer")

        if "debug" in config_data and not isinstance(config_data["debug"], bool):
            errors.append("Debug must be a boolean")

        # Check for unknown top-level keys
        known_keys = set([
            "environment", "debug", "host", "port", "logging", "zhipuai",
            "hot_reload", "devices", "adapters", "version"
        ])
        unknown_keys = set(config_data.keys()) - known_keys
        if unknown_keys:
            warnings.append(f"Unknown configuration keys: {', '.join(unknown_keys)}")

        return errors, warnings

    def _additional_validation(self, config_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Perform additional validation checks."""
        errors = []
        warnings = []

        # Validate device configurations if present
        if "devices" in config_data:
            devices = config_data["devices"]
            if isinstance(devices, list):
                device_ids = []
                for i, device in enumerate(devices):
                    if isinstance(device, dict) and "id" in device:
                        device_id = device["id"]
                        if device_id in device_ids:
                            errors.append(f"Duplicate device ID: {device_id}")
                        device_ids.append(device_id)

                        # Validate device type
                        if "type" in device:
                            device_type = device["type"]
                            valid_types = ["thermostat", "light", "switch", "sensor", "camera", "lock"]
                            if device_type not in valid_types:
                                warnings.append(f"Unknown device type: {device_type}")

        # Validate adapter configurations if present
        if "adapters" in config_data:
            adapters = config_data["adapters"]
            if isinstance(adapters, list):
                adapter_ids = []
                for i, adapter in enumerate(adapters):
                    if isinstance(adapter, dict) and "id" in adapter:
                        adapter_id = adapter["id"]
                        if adapter_id in adapter_ids:
                            errors.append(f"Duplicate adapter ID: {adapter_id}")
                        adapter_ids.append(adapter_id)

        return errors, warnings

    def _runtime_validation(self, app_settings: AppSettings) -> Tuple[List[str], List[str]]:
        """Perform runtime-specific validation."""
        errors = []
        warnings = []

        # Check if log directory is accessible
        if app_settings.logging.file_path:
            log_path = Path(app_settings.logging.file_path)
            if log_path.exists() and not self._check_write_permission(log_path):
                errors.append(f"Cannot write to log file: {log_path}")

        # Check network settings
        if app_settings.host == "0.0.0.0" and app_settings.environment.value == "production":
            warnings.append("Binding to all interfaces (0.0.0.0) in production")

        # Check performance implications
        if app_settings.logging.serialize and app_settings.environment.value == "development":
            warnings.append("JSON serialization enabled in development (may impact performance)")

        return errors, warnings

    def _check_write_permission(self, path: Path) -> bool:
        """Check if we have write permission to a path."""
        try:
            test_file = path / ".synhome_write_test"
            test_file.touch()
            test_file.unlink()
            return True
        except (OSError, PermissionError):
            return False

    def _store_validation_report(self, report: ValidationReport) -> None:
        """Store validation report in history."""
        self.validation_history.append(report)

        # Keep only recent reports
        if len(self.validation_history) > self.max_history_size:
            self.validation_history = self.validation_history[-self.max_history_size:]


# Global validation service instance
_validation_service: Optional[ConfigurationValidationService] = None


def get_validation_service() -> ConfigurationValidationService:
    """Get or create the global validation service."""
    global _validation_service
    if _validation_service is None:
        _validation_service = ConfigurationValidationService()
    return _validation_service


def validate_config_file(
    config_path: Union[str, Path],
    strict_mode: bool = False
) -> ValidationResult:
    """Validate a configuration file."""
    service = get_validation_service()
    return service.validate_configuration_file(config_path, strict_mode)


def validate_config_data(config_data: Dict[str, Any]) -> ValidationResult:
    """Validate configuration data."""
    service = get_validation_service()
    return service.validate_configuration_data(config_data)


def validate_app_settings(app_settings: AppSettings) -> ValidationResult:
    """Validate AppSettings instance."""
    service = get_validation_service()
    return service.validate_app_settings(app_settings)


def perform_config_health_check(app_settings: AppSettings) -> ValidationResult:
    """Perform configuration health check."""
    service = get_validation_service()
    return service.perform_health_check(app_settings)