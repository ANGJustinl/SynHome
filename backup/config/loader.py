"""
Configuration loading utilities for SynHome.

Provides:
- Environment-specific configuration loading
- Configuration file merging and inheritance
- Environment variable override handling
- Configuration caching and hot reload support
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
from loguru import logger

from .models import AppSettings
from .validator import ConfigValidator
from .legacy import LegacyConfigAdapter, is_legacy_config


@dataclass
class ConfigLoadOptions:
    """Options for configuration loading."""
    environment: Optional[str] = None
    config_dir: Optional[Union[str, Path]] = None
    env_file: Optional[Union[str, Path]] = None
    validate: bool = True
    migrate_legacy: bool = True
    cache_enabled: bool = True
    allow_overrides: bool = True


class ConfigLoader:
    """Configuration loader with environment and file support."""

    def __init__(self, options: Optional[ConfigLoadOptions] = None):
        """
        Initialize configuration loader.

        Args:
            options: Loading options
        """
        self.options = options or ConfigLoadOptions()
        self.validator = ConfigValidator()
        self.legacy_adapter = LegacyConfigAdapter()
        self._config_cache: Dict[str, Any] = {}
        self._load_history: List[Dict[str, Any]] = []

    def load_configuration(
        self,
        config_file: Optional[Union[str, Path]] = None,
        **overrides
    ) -> AppSettings:
        """
        Load complete application configuration.

        Args:
            config_file: Optional main configuration file
            **overrides: Configuration overrides

        Returns:
            Loaded and validated AppSettings
        """
        load_start = logger._core.now().timestamp()

        # Determine configuration directory
        config_dir = self._resolve_config_dir()

        # Load base configuration
        config_data = self._load_base_config(config_dir, config_file)

        # Load environment-specific configuration
        env_config = self._load_environment_config(config_dir)
        if env_config:
            config_data.update(env_config)

        # Apply environment variable overrides
        if self.options.allow_overrides:
            env_var_overrides = self._load_env_var_overrides()
            if env_var_overrides:
                config_data = self._merge_configs(config_data, env_var_overrides)

        # Apply explicit overrides
        if overrides:
            config_data = self._merge_configs(config_data, overrides)

        # Validate and migrate configuration if needed
        if is_legacy_config(config_data):
            if self.options.migrate_legacy:
                logger.info("Detected legacy configuration format, attempting migration")
                config_data, migration_warnings = self.legacy_adapter.migrate_config(config_data)
                for warning in migration_warnings:
                    logger.warning(f"Migration warning: {warning}")
            else:
                logger.warning("Legacy configuration format detected but migration is disabled")

        # Validate configuration
        if self.options.validate:
            is_valid, errors, warnings = self.validator.validate_environment_config(
                AppSettings(**config_data)
            )
            if not is_valid:
                raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
            for warning in warnings:
                logger.warning(f"Configuration warning: {warning}")

        # Create AppSettings instance
        app_settings = AppSettings(**config_data)

        # Record load history
        load_duration = logger._core.now().timestamp() - load_start
        self._record_load(load_duration, config_file, env_config is not None, bool(overrides))

        logger.info(f"Configuration loaded successfully in {load_duration:.3f}s")
        return app_settings

    def _resolve_config_dir(self) -> Path:
        """Resolve configuration directory path."""
        if self.options.config_dir:
            config_dir = Path(self.options.config_dir)
        elif "SYNHOME_CONFIG_DIR" in os.environ:
            config_dir = Path(os.environ["SYNHOME_CONFIG_DIR"])
        else:
            # Default to project config directory
            config_dir = Path("config")

        if not config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {config_dir}")

        return config_dir

    def _load_base_config(
        self,
        config_dir: Path,
        config_file: Optional[Union[str, Path]]
    ) -> Dict[str, Any]:
        """Load base configuration."""
        if config_file:
            # Load specified configuration file
            config_path = Path(config_file)
            if not config_path.is_absolute():
                config_path = config_dir / config_path

            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")

            return self._load_config_file(config_path)

        else:
            # Look for default configuration files
            default_files = ["base.yaml", "base.yml", "config.yaml", "config.yml", "app.yaml"]

            for filename in default_files:
                config_path = config_dir / filename
                if config_path.exists():
                    logger.debug(f"Loading base configuration from: {config_path}")
                    return self._load_config_file(config_path)

            # No base configuration found, return empty dict
            logger.warning("No base configuration file found, using defaults")
            return {}

    def _load_environment_config(self, config_dir: Path) -> Optional[Dict[str, Any]]:
        """Load environment-specific configuration."""
        environment = self._determine_environment()

        if not environment:
            return None

        # Look for environment-specific configuration
        profiles_dir = config_dir / "profiles"
        env_files = [
            profiles_dir / f"{environment}.yaml",
            profiles_dir / f"{environment}.yml",
            config_dir / f"{environment}.yaml",
            config_dir / f"{environment}.yml"
        ]

        for env_file in env_files:
            if env_file.exists():
                logger.debug(f"Loading environment configuration from: {env_file}")
                return self._load_config_file(env_file)

        logger.debug(f"No environment-specific configuration found for: {environment}")
        return None

    def _determine_environment(self) -> Optional[str]:
        """Determine current environment."""
        # Check explicit option
        if self.options.environment:
            return self.options.environment

        # Check environment variable
        if "SYNHOME_ENVIRONMENT" in os.environ:
            return os.environ["SYNHOME_ENVIRONMENT"]

        # Check from .env file
        if self.options.env_file:
            env_file = Path(self.options.env_file)
        else:
            env_file = Path(".env")

        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('SYNHOME_ENVIRONMENT='):
                            return line.split('=', 1)[1].strip('"\'')
            except Exception:
                pass

        return None

    def _load_env_var_overrides(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables."""
        overrides = {}
        prefix = "SYNHOME_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert environment variable name to nested config path
                config_key = key[len(prefix):].lower()

                # Handle nested keys with double underscore
                if '__' in config_key:
                    # Handle multiple levels of nesting
                    parts = config_key.split('__')
                    current = overrides
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]

                    # Convert value to appropriate type
                    current[parts[-1]] = self._convert_env_value(value)
                else:
                    # Handle simple keys
                    overrides[config_key] = self._convert_env_value(value)

        return overrides

    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean conversion
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False

        # Numeric conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        # JSON conversion
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        # Default to string
        return value

    def _load_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from file."""
        if config_path.suffix.lower() in ['.yaml', '.yml']:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {config_path}: {e}")
        elif config_path.suffix.lower() == '.json':
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {config_path}: {e}")
        else:
            raise ValueError(f"Unsupported configuration file format: {config_path.suffix}")

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._merge_configs(result[key], value)
            else:
                # Override or add new value
                result[key] = value

        return result

    def _record_load(
        self,
        duration: float,
        config_file: Optional[Union[str, Path]],
        has_env_config: bool,
        has_overrides: bool
    ) -> None:
        """Record configuration load history."""
        record = {
            "timestamp": logger._core.now().isoformat(),
            "duration_seconds": duration,
            "config_file": str(config_file) if config_file else None,
            "environment": self._determine_environment(),
            "has_env_config": has_env_config,
            "has_overrides": has_overrides,
            "validation_enabled": self.options.validate,
            "migration_enabled": self.options.migrate_legacy
        }

        self._load_history.append(record)

        # Keep only recent history (last 100 entries)
        if len(self._load_history) > 100:
            self._load_history = self._load_history[-100:]

    def get_load_history(self) -> List[Dict[str, Any]]:
        """Get configuration load history."""
        return self._load_history.copy()

    def reload_configuration(self) -> AppSettings:
        """Reload configuration with current settings."""
        logger.info("Reloading configuration...")
        return self.load_configuration()

    def validate_configuration_file(self, config_path: Union[str, Path]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a configuration file without loading it.

        Args:
            config_path: Path to configuration file

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        try:
            config_data = self._load_config_file(Path(config_path))
            return self.validator.validate_config_file(str(config_path))
        except Exception as e:
            return False, [f"Failed to load configuration file: {e}"], []

    def list_available_configs(self, config_dir: Optional[Union[str, Path]] = None) -> Dict[str, List[str]]:
        """
        List available configuration files.

        Args:
            config_dir: Configuration directory to scan

        Returns:
            Dictionary of configuration file types and their paths
        """
        config_dir = Path(config_dir) if config_dir else self._resolve_config_dir()

        configs = {
            "base": [],
            "environments": [],
            "profiles": [],
            "other": []
        }

        if not config_dir.exists():
            return configs

        # Scan main config directory
        for config_file in config_dir.glob("*.yaml"):
            if config_file.name.startswith("base"):
                configs["base"].append(str(config_file))
            elif config_file.name in ["development.yaml", "testing.yaml", "production.yaml"]:
                configs["environments"].append(str(config_file))
            else:
                configs["other"].append(str(config_file))

        # Scan profiles directory
        profiles_dir = config_dir / "profiles"
        if profiles_dir.exists():
            for profile_file in profiles_dir.glob("*.yaml"):
                configs["profiles"].append(str(profile_file))

        return configs

    def export_configuration(
        self,
        app_settings: AppSettings,
        output_path: Union[str, Path],
        format_type: str = "yaml"
    ) -> None:
        """
        Export configuration to file.

        Args:
            app_settings: Configuration to export
            output_path: Output file path
            format_type: Export format ('yaml' or 'json')
        """
        output_path = Path(output_path)
        config_dict = app_settings.model_dump()

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type.lower() == "yaml":
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        elif format_type.lower() == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

        logger.info(f"Configuration exported to: {output_path}")

    def create_config_template(
        self,
        output_path: Union[str, Path],
        environment: str = "development"
    ) -> None:
        """
        Create a configuration template file.

        Args:
            output_path: Output path for template
            environment: Target environment
        """
        # Create default configuration
        default_config = {
            "environment": environment,
            "debug": environment == "development",
            "host": "0.0.0.0",
            "port": 8000,
            "logging": {
                "level": "DEBUG" if environment == "development" else "INFO",
                "file_path": "logs/app.log",
                "console_output": True,
                "serialize": environment == "production"
            },
            "zhipuai": {
                "enabled": False,
                "api_key": "",
                "model": "chatglm-turbo"
            },
            "hot_reload": {
                "enabled": environment == "development",
                "debounce_seconds": 1.0
            },
            "devices": [],
            "adapters": []
        }

        self.export_configuration(AppSettings(**default_config), output_path)
        logger.info(f"Configuration template created: {output_path}")


# Global configuration loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(options: Optional[ConfigLoadOptions] = None) -> ConfigLoader:
    """Get or create the global configuration loader."""
    global _config_loader
    if _config_loader is None or options:
        _config_loader = ConfigLoader(options)
    return _config_loader


def load_config(
    config_file: Optional[Union[str, Path]] = None,
    **overrides
) -> AppSettings:
    """
    Load application configuration.

    Args:
        config_file: Optional configuration file path
        **overrides: Configuration overrides

    Returns:
        Loaded AppSettings
    """
    loader = get_config_loader()
    return loader.load_configuration(config_file, **overrides)


def load_config_from_env() -> AppSettings:
    """Load configuration from environment variables and default locations."""
    return load_config()


def validate_config_file(config_path: Union[str, Path]) -> Tuple[bool, List[str], List[str]]:
    """Validate a configuration file."""
    loader = get_config_loader()
    return loader.validate_configuration_file(config_path)


def create_config_template(
    output_path: Union[str, Path],
    environment: str = "development"
) -> None:
    """Create a configuration template file."""
    loader = get_config_loader()
    loader.create_config_template(output_path, environment)