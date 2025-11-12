"""
Legacy configuration adapter for backward compatibility in SynHome.

Provides:
- Migration utilities for old configuration formats
- Backward compatibility layer
- Configuration upgrade paths
- Legacy format validation
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass
from loguru import logger

from .models import AppSettings, LogConfig, ZhipuAIConfig, HotReloadConfig
from .devices import DeviceConfig, AdapterConfig, SmartHomeConfig


@dataclass
class LegacyFormat:
    """Legacy configuration format information."""
    version: str
    format_type: str  # "yaml", "json", "dict"
    description: str
    migration_path: str


class LegacyConfigAdapter:
    """Adapter for handling legacy configuration formats."""

    def __init__(self):
        """Initialize legacy config adapter."""
        self.supported_formats = {
            "v1.0": LegacyFormat(
                version="1.0",
                format_type="yaml",
                description="Original YAML configuration format",
                migration_path="migrate_v1_to_v2"
            ),
            "v1.1": LegacyFormat(
                version="1.1",
                format_type="yaml",
                description="YAML with basic device configuration",
                migration_path="migrate_v1_1_to_v2"
            ),
            "v2.0": LegacyFormat(
                version="2.0",
                format_type="yaml",
                description="Current Pydantic-based format",
                migration_path="none"
            )
        }
        self.migration_history = []

    def detect_format_version(self, config_data: Dict[str, Any]) -> Optional[str]:
        """
        Detect the format version of configuration data.

        Args:
            config_data: Configuration dictionary

        Returns:
            Detected version string or None if unknown
        """
        # Check for version field
        if "version" in config_data:
            version = str(config_data["version"])
            if version in self.supported_formats:
                return version

        # Check for v1.0 format indicators
        if "smart_home" in config_data and "zhipuai" in config_data:
            return "v1.0"

        # Check for v1.1 format indicators
        if "devices" in config_data and "adapters" in config_data:
            if "logging" not in config_data or not isinstance(config_data.get("logging"), dict):
                return "v1.1"

        # Default to current format
        return "v2.0"

    def migrate_config(
        self,
        config_data: Dict[str, Any],
        target_version: str = "v2.0"
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Migrate configuration to target version.

        Args:
            config_data: Source configuration data
            target_version: Target format version

        Returns:
            Tuple of (migrated_config, migration_warnings)
        """
        current_version = self.detect_format_version(config_data)

        if current_version == target_version:
            return config_data.copy(), []

        if current_version not in self.supported_formats:
            raise ValueError(f"Unsupported configuration format: {current_version}")

        if target_version not in self.supported_formats:
            raise ValueError(f"Unsupported target format: {target_version}")

        # Perform migration
        migrated_data = config_data.copy()
        warnings = []

        # Apply migration steps based on current version
        if current_version == "v1.0":
            migrated_data, warnings = self.migrate_v1_to_v2(migrated_data)
        elif current_version == "v1.1":
            migrated_data, warnings = self.migrate_v1_1_to_v2(migrated_data)

        # Record migration
        migration_record = {
            "timestamp": logger._core.now().isoformat(),
            "from_version": current_version,
            "to_version": target_version,
            "warnings": warnings
        }
        self.migration_history.append(migration_record)

        return migrated_data, warnings

    def migrate_v1_to_v2(self, config_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Migrate v1.0 configuration to v2.0 format.

        Args:
            config_data: v1.0 configuration data

        Returns:
            Tuple of (migrated_config, warnings)
        """
        warnings = []
        migrated = {}

        # Migrate basic settings
        if "smart_home" in config_data:
            smart_home = config_data["smart_home"]

            # Map old fields to new structure
            if "host" in smart_home:
                migrated["host"] = smart_home["host"]
            else:
                migrated["host"] = "0.0.0.0"
                warnings.append("Default host set to 0.0.0.0")

            if "port" in smart_home:
                migrated["port"] = smart_home["port"]
            else:
                migrated["port"] = 8000
                warnings.append("Default port set to 8000")

            if "debug" in smart_home:
                migrated["debug"] = smart_home["debug"]
            else:
                migrated["debug"] = False

            if "environment" in smart_home:
                migrated["environment"] = smart_home["environment"]
            else:
                migrated["environment"] = "development"
                warnings.append("Default environment set to development")

        # Migrate ZhipuAI configuration
        if "zhipuai" in config_data:
            zhipuai_config = {
                "enabled": True,
                "api_key": config_data["zhipuai"].get("api_key", ""),
                "model": config_data["zhipuai"].get("model", "chatglm-turbo"),
                "timeout": config_data["zhipuai"].get("timeout", 30),
                "max_retries": config_data["zhipuai"].get("max_retries", 3)
            }
            migrated["zhipuai"] = zhipuai_config
        else:
            migrated["zhipuai"] = {"enabled": False}
            warnings.append("ZhipuAI disabled - no configuration found")

        # Add default logging configuration
        migrated["logging"] = {
            "level": "INFO",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            "file_path": "logs/app.log",
            "max_size": "100 MB",
            "retention": "30 days",
            "compression": "zip",
            "rotation": "1 day",
            "serialize": False,
            "enqueue": True,
            "console_output": True
        }
        warnings.append("Default logging configuration added")

        # Migrate devices and adapters if present
        if "devices" in config_data.get("smart_home", {}):
            migrated["devices"] = config_data["smart_home"]["devices"]
        else:
            migrated["devices"] = []

        if "adapters" in config_data.get("smart_home", {}):
            migrated["adapters"] = config_data["smart_home"]["adapters"]
        else:
            migrated["adapters"] = []

        # Add default hot reload configuration
        migrated["hot_reload"] = {
            "enabled": True,
            "watch_files": ["*.yaml", "*.yml", "*.json"],
            "debounce_seconds": 1.0,
            "reloadable_sections": ["logging", "zhipuai", "devices", "adapters"]
        }

        # Add version information
        migrated["version"] = "2.0"

        return migrated, warnings

    def migrate_v1_1_to_v2(self, config_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Migrate v1.1 configuration to v2.0 format.

        Args:
            config_data: v1.1 configuration data

        Returns:
            Tuple of (migrated_config, warnings)
        """
        warnings = []
        migrated = config_data.copy()

        # Ensure required fields have defaults
        if "environment" not in migrated:
            migrated["environment"] = "development"
            warnings.append("Default environment set to development")

        if "debug" not in migrated:
            migrated["debug"] = migrated.get("environment") == "development"
            warnings.append("Debug mode inferred from environment")

        # Add or update logging configuration
        if "logging" not in migrated:
            migrated["logging"] = {
                "level": "INFO",
                "file_path": "logs/app.log",
                "console_output": True
            }
            warnings.append("Default logging configuration added")
        else:
            # Ensure logging has required fields
            logging_config = migrated["logging"]
            if "format" not in logging_config:
                logging_config["format"] = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
                warnings.append("Default log format added")

            if "enqueue" not in logging_config:
                logging_config["enqueue"] = True
                warnings.append("Log enqueueing enabled for performance")

        # Add ZhipuAI configuration if missing
        if "zhipuai" not in migrated:
            migrated["zhipuai"] = {"enabled": False}
            warnings.append("ZhipuAI disabled - no configuration found")

        # Add hot reload configuration
        if "hot_reload" not in migrated:
            migrated["hot_reload"] = {
                "enabled": True,
                "watch_files": ["*.yaml", "*.yml", "*.json"],
                "debounce_seconds": 1.0,
                "reloadable_sections": ["logging", "zhipuai", "devices", "adapters"]
            }
            warnings.append("Default hot reload configuration added")

        # Update version
        migrated["version"] = "2.0"

        return migrated, warnings

    def load_legacy_config(self, config_path: Union[str, Path]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Load and migrate a legacy configuration file.

        Args:
            config_path: Path to configuration file

        Returns:
            Tuple of (migrated_config, migration_warnings)
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Load configuration based on file extension
        try:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
            elif config_path.suffix.lower() == '.json':
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {config_path.suffix}")

        except Exception as e:
            raise ValueError(f"Failed to parse configuration file {config_path}: {e}")

        # Detect and migrate configuration
        version = self.detect_format_version(config_data)
        logger.info(f"Detected configuration format version: {version}")

        if version == "v2.0":
            return config_data, []

        migrated_config, warnings = self.migrate_config(config_data)
        logger.info(f"Migrated configuration from {version} to v2.0")

        if warnings:
            logger.warning(f"Migration warnings: {'; '.join(warnings)}")

        return migrated_config, warnings

    def validate_legacy_config(self, config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate legacy configuration format.

        Args:
            config_data: Configuration data to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        version = self.detect_format_version(config_data)
        errors = []

        if version == "v2.0":
            # Use current validation
            try:
                AppSettings(**config_data)
                return True, []
            except Exception as e:
                return False, [str(e)]

        # Legacy format validation
        if version == "v1.0":
            if "smart_home" not in config_data:
                errors.append("Missing 'smart_home' section")
            else:
                smart_home = config_data["smart_home"]
                if "host" not in smart_home:
                    errors.append("Missing 'host' in smart_home configuration")
                if "port" not in smart_home:
                    errors.append("Missing 'port' in smart_home configuration")

        elif version == "v1.1":
            if "devices" not in config_data:
                errors.append("Missing 'devices' section")
            if "adapters" not in config_data:
                errors.append("Missing 'adapters' section")

        return len(errors) == 0, errors

    def backup_legacy_config(self, config_path: Union[str, Path]) -> Path:
        """
        Create a backup of legacy configuration before migration.

        Args:
            config_path: Path to configuration file

        Returns:
            Path to backup file
        """
        config_path = Path(config_path)

        # Generate backup filename
        timestamp = logger._core.now().strftime("%Y%m%d_%H%M%S")
        backup_path = config_path.parent / f"{config_path.stem}_backup_{timestamp}{config_path.suffix}"

        # Copy file
        import shutil
        shutil.copy2(config_path, backup_path)

        logger.info(f"Configuration backup created: {backup_path}")
        return backup_path

    def get_migration_history(self) -> List[Dict[str, Any]]:
        """Get history of configuration migrations."""
        return self.migration_history.copy()

    def clear_migration_history(self) -> None:
        """Clear migration history."""
        self.migration_history.clear()


# Global legacy adapter instance
_legacy_adapter = LegacyConfigAdapter()


def get_legacy_adapter() -> LegacyConfigAdapter:
    """Get the global legacy configuration adapter."""
    return _legacy_adapter


def migrate_config_file(
    config_path: Union[str, Path],
    backup: bool = True,
    output_path: Optional[Union[str, Path]] = None
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Migrate a configuration file to the current format.

    Args:
        config_path: Path to legacy configuration file
        backup: Whether to create a backup
        output_path: Output path for migrated config (defaults to original)

    Returns:
        Tuple of (migrated_config, warnings)
    """
    config_path = Path(config_path)

    if backup:
        _legacy_adapter.backup_legacy_config(config_path)

    # Load and migrate configuration
    migrated_config, warnings = _legacy_adapter.load_legacy_config(config_path)

    # Save migrated configuration
    output_path = output_path or config_path
    output_path = Path(output_path)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(migrated_config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Migrated configuration saved to: {output_path}")

    except Exception as e:
        raise ValueError(f"Failed to save migrated configuration: {e}")

    return migrated_config, warnings


def validate_and_migrate_config(
    config_data: Dict[str, Any],
    target_version: str = "v2.0"
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    Validate and migrate configuration data.

    Args:
        config_data: Configuration data to validate and migrate
        target_version: Target format version

    Returns:
        Tuple of (is_valid, migrated_config, messages)
    """
    adapter = get_legacy_adapter()

    # Check if migration is needed
    current_version = adapter.detect_format_version(config_data)

    if current_version == target_version:
        # No migration needed, just validate
        try:
            AppSettings(**config_data)
            return True, config_data, ["Configuration is valid and up-to-date"]
        except Exception as e:
            return False, config_data, [f"Validation error: {e}"]

    # Migrate configuration
    try:
        migrated_config, warnings = adapter.migrate_config(config_data, target_version)

        # Validate migrated configuration
        try:
            AppSettings(**migrated_config)
            return True, migrated_config, warnings + ["Migration and validation successful"]
        except Exception as e:
            return False, migrated_config, warnings + [f"Post-migration validation error: {e}"]

    except Exception as e:
        return False, config_data, [f"Migration error: {e}"]


def is_legacy_config(config_data: Dict[str, Any]) -> bool:
    """
    Check if configuration data is in legacy format.

    Args:
        config_data: Configuration data to check

    Returns:
        True if configuration is in legacy format
    """
    version = _legacy_adapter.detect_format_version(config_data)
    return version != "v2.0"