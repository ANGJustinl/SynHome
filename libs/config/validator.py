"""
Configuration validation utilities for SynHome.

Provides comprehensive validation for configuration files with clear error messages
and support for multiple configuration sources.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from pydantic import ValidationError
from .models import AppSettings

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Configuration validation error."""
    def __init__(self, errors: List[str], warnings: List[str] = None):
        self.errors = errors
        self.warnings = warnings or []
        super().__init__(f"Configuration validation failed: {'; '.join(errors)}")


class ConfigValidator:
    """Configuration validator with comprehensive error reporting."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_config_file(self, config_path: str) -> Tuple[bool, List[str], List[str]]:
        """Validate a configuration file."""
        self.errors.clear()
        self.warnings.clear()

        path = Path(config_path)

        # Check file existence
        if not path.exists():
            self.errors.append(f"Configuration file does not exist: {config_path}")
            return False, self.errors, self.warnings

        # Check file readability
        if not path.is_file():
            self.errors.append(f"Path is not a file: {config_path}")
            return False, self.errors, self.warnings

        # Check file extension
        if path.suffix not in ['.yaml', '.yml', '.json']:
            self.warnings.append(
                f"Configuration file has unusual extension: {path.suffix}. "
                f"Expected .yaml, .yml, or .json"
            )

        # Validate using appropriate loader
        try:
            if path.suffix == '.json':
                import json
                with open(path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:  # YAML
                import yaml
                with open(path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)

            # Validate configuration structure
            self._validate_config_structure(config_data)

            # Try to create configuration model (this validates the data types)
            try:
                # Use AppSettings for all configuration validation
                AppSettings(**config_data)

            except ValidationError as e:
                # Parse Pydantic errors and make them user-friendly
                pydantic_errors = self._format_pydantic_errors(e)
                self.errors.extend(pydantic_errors)

        except Exception as e:
            self.errors.append(f"Failed to parse configuration file {config_path}: {str(e)}")

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_config_structure(self, config_data: Dict[str, Any]) -> None:
        """Validate the basic structure of configuration data."""
        if not isinstance(config_data, dict):
            self.errors.append("Configuration must be a dictionary/object")

        # Check for common required sections in demo.yaml
        if 'devices' in config_data:
            self._validate_devices_section(config_data['devices'])

        if 'adapters' in config_data:
            self._validate_adapters_section(config_data['adapters'])

    def _validate_devices_section(self, devices: Any) -> None:
        """Validate the devices section of configuration."""
        if not isinstance(devices, list):
            self.errors.append("'devices' section must be a list")
            return

        device_ids = set()
        for i, device in enumerate(devices):
            if not isinstance(device, dict):
                self.errors.append(f"Device {i} must be a dictionary")
                continue

            # Check required device fields
            required_fields = ['id', 'name', 'type', 'capabilities']
            for field in required_fields:
                if field not in device:
                    self.errors.append(f"Device {i} missing required field: {field}")

            # Check device ID uniqueness
            if 'id' in device:
                device_id = device['id']
                if device_id in device_ids:
                    self.errors.append(f"Duplicate device ID: {device_id}")
                device_ids.add(device_id)

            # Validate capabilities if present
            if 'capabilities' in device:
                self._validate_device_capabilities(device['capabilities'], i)

    def _validate_device_capabilities(self, capabilities: Any, device_index: int) -> None:
        """Validate device capabilities."""
        if not isinstance(capabilities, dict):
            self.errors.append(f"Device {device_index} capabilities must be a dictionary")
            return

        for cap_name, cap_config in capabilities.items():
            if not isinstance(cap_config, dict):
                self.errors.append(
                    f"Device {device_index} capability '{cap_name}' must be a dictionary"
                )
                continue

            # Check required capability fields
            if 'type' not in cap_config:
                self.errors.append(
                    f"Device {device_index} capability '{cap_name}' missing required field: type"
                )

            # Validate capability type
            cap_type = cap_config.get('type')
            if cap_type == 'number':
                if 'min_value' not in cap_config or 'max_value' not in cap_config:
                    self.errors.append(
                        f"Device {device_index} capability '{cap_name}' of type 'number' "
                        f"must have both 'min_value' and 'max_value'"
                    )
            elif cap_config.get('min_value', 0) >= cap_config.get('max_value', 0):
                self.errors.append(
                    f"Device {device_index} capability '{cap_name}' min_value must be "
                    f"less than max_value"
                )

            elif cap_type == 'enum':
                if 'values' not in cap_config or not cap_config['values']:
                    self.errors.append(
                        f"Device {device_index} capability '{cap_name}' of type 'enum' "
                        f"must have 'values' list"
                    )

            elif cap_type == 'switch':
                if 'states' not in cap_config or len(cap_config['states']) != 2:
                    self.errors.append(
                        f"Device {device_index} capability '{cap_name}' of type 'switch' "
                        f"must have exactly 2 states"
                    )

    def _validate_adapters_section(self, adapters: Any) -> None:
        """Validate the adapters section of configuration."""
        if not isinstance(adapters, list):
            self.errors.append("'adapters' section must be a list")
            return

        adapter_ids = set()
        for i, adapter in enumerate(adapters):
            if not isinstance(adapter, dict):
                self.errors.append(f"Adapter {i} must be a dictionary")
                continue

            # Check required adapter fields
            required_fields = ['id', 'type', 'config']
            for field in required_fields:
                if field not in adapter:
                    self.errors.append(f"Adapter {i} missing required field: {field}")

            # Check adapter ID uniqueness
            if 'id' in adapter:
                adapter_id = adapter['id']
                if adapter_id in adapter_ids:
                    self.errors.append(f"Duplicate adapter ID: {adapter_id}")
                adapter_ids.add(adapter_id)

            # Validate adapter type
            adapter_type = adapter.get('type')
            valid_types = ['websocket', 'mqtt', 'http', 'serial', 'modbus', 'zigbee', 'gpio']
            if adapter_type not in valid_types:
                self.errors.append(
                    f"Adapter {i} has invalid type '{adapter_type}'. "
                    f"Valid types: {', '.join(valid_types)}"
                )

            # Validate adapter config
            if 'config' in adapter:
                self._validate_adapter_config(adapter['config'], adapter_type, i)

    def _validate_adapter_config(self, config: Any, adapter_type: str, adapter_index: int) -> None:
        """Validate adapter-specific configuration."""
        if not isinstance(config, dict):
            self.errors.append(f"Adapter {adapter_index} config must be a dictionary")
            return

        if adapter_type == "websocket":
            required_fields = ["url"]
            for field in required_fields:
                if field not in config:
                    self.errors.append(
                        f"WebSocket adapter {adapter_index} requires '{field}' in config"
                    )

        elif adapter_type == "mqtt":
            required_fields = ["host"]
            for field in required_fields:
                if field not in config:
                    self.errors.append(
                        f"MQTT adapter {adapter_index} requires '{field}' in config"
                    )

    def _format_pydantic_errors(self, validation_error: ValidationError) -> List[str]:
        """Format Pydantic validation errors into user-friendly messages."""
        errors = []
        for error in validation_error.errors():
            loc = " -> ".join(str(x) for x in error.loc())
            msg = error.msg
            errors.append(f"Configuration error at '{loc}': {msg}")
        return errors

    def validate_environment_config(self, app_settings: AppSettings) -> Tuple[bool, List[str], List[str]]:
        """Validate application settings."""
        self.errors.clear()
        self.warnings.clear()

        # Check port range
        if not (1 <= app_settings.port <= 65535):
            self.errors.append(f"Port {app_settings.port} is out of valid range (1-65535)")

        # Check environment consistency
        if app_settings.debug and app_settings.environment == "production":
            self.warnings.append(
                "Debug mode should not be enabled in production environment"
            )

        # Check logging configuration
        if app_settings.logging.file_path:
            log_path = Path(app_settings.logging.file_path)
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.errors.append(f"Cannot create log directory: {e}")

        # Check ZhipuAI configuration if enabled
        if app_settings.zhipuai and app_settings.zhipuai.enabled:
            if not app_settings.zhipuai.api_key or len(app_settings.zhipuai.api_key) < 10:
                self.errors.append("ZhipuAI API key must be at least 10 characters when enabled")


def validate_config(config: AppSettings) -> Tuple[bool, List[str]]:
    """
    Simple validation function for AppSettings.

    Args:
        config: The configuration to validate

    Returns:
        Tuple of (is_valid, errors)
    """
    validator = ConfigValidator()
    validator.validate_app_settings(config)

    return len(validator.errors) == 0, validator.errors