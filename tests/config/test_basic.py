"""
Basic configuration system tests for SynHome.
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from libs.config import load_config, AppSettings, validate_config


class TestConfigLoading:
    """Test basic configuration loading functionality."""

    def test_load_minimal_config(self):
        """Test loading minimal default configuration."""
        # Should not raise any errors with default settings
        config = load_config()
        assert isinstance(config, AppSettings)
        assert config.environment.value in ["development", "testing", "production"]
        assert isinstance(config.debug, bool)
        assert isinstance(config.port, int)
        assert 1 <= config.port <= 65535

    def test_load_config_with_overrides(self):
        """Test loading configuration with overrides."""
        config = load_config(
            environment="testing",
            debug=False,
            port=9000
        )
        assert config.environment.value == "testing"
        assert config.debug is False
        assert config.port == 9000

    def test_load_config_from_file(self):
        """Test loading configuration from file."""
        test_config = {
            "environment": "development",
            "debug": True,
            "host": "127.0.0.1",
            "port": 8080,
            "logging": {
                "level": "DEBUG",
                "console_output": True
            },
            "zhipuai": {"enabled": False},
            "hot_reload": {"enabled": False},
            "devices": [],
            "adapters": []
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            config_file = f.name

        try:
            config = load_config(config_file)
            assert config.environment.value == "development"
            assert config.debug is True
            assert config.host == "127.0.0.1"
            assert config.port == 8080
        finally:
            Path(config_file).unlink()

    def test_load_config_from_nonexistent_file(self):
        """Test loading configuration from non-existent file."""
        # Should use default configuration and not raise error
        config = load_config("nonexistent_file.yaml")
        assert isinstance(config, AppSettings)

    def test_validate_valid_config(self):
        """Test validating valid configuration data."""
        valid_config = {
            "environment": "development",
            "debug": False,
            "host": "localhost",
            "port": 8000,
            "logging": {
                "level": "INFO",
                "console_output": True
            },
            "zhipuai": {"enabled": False},
            "hot_reload": {"enabled": False},
            "devices": [],
            "adapters": []
        }

        assert validate_config(valid_config) is True

    def test_validate_invalid_config(self):
        """Test validating invalid configuration data."""
        invalid_config = {
            "environment": "invalid_env",  # Invalid enum value
            "debug": "not_boolean",     # Invalid type
            "port": "invalid_port",       # Invalid type
            "logging": {
                "level": "INVALID_LEVEL"  # Invalid log level
            },
            "zhipuai": {"enabled": False},
            "hot_reload": {"enabled": False},
            "devices": [],
            "adapters": []
        }

        # Should catch validation errors
        with pytest.raises(ValueError):
            AppSettings(**invalid_config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])