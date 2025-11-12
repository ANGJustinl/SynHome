# Quick Start Guide: SynHome Configuration and Logging Optimization

**Purpose**: This guide helps developers quickly understand and implement the simplified configuration and logging system in SynHome.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Basic Configuration](#basic-configuration)
4. [Logging Setup](#logging-setup)
5. [Environment Management](#environment-management)
6. [FastAPI Integration](#fastapi-integration)
7. [API Usage](#api-usage)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.12+
- SynHome project structure
- Administrator privileges for configuration changes

## Installation

### 1. Add Dependencies

Add to your `requirements.txt` or `pyproject.toml`:

```txt
pydantic>=2.0.0
pydantic-settings>=2.0.0
loguru>=0.7.0
watchdog>=3.0.0
aiofiles>=23.0.0
```

Or using pip:

```bash
pip install "pydantic>=2.0.0" "pydantic-settings>=2.0.0" "loguru>=0.7.0" "watchdog>=3.0.0" aiofiles
```

### 2. Update Project Structure

Create new directories in your SynHome project:

```bash
mkdir -p libs/config libs/logging logs config/profiles
```

The simplified structure includes:
- `libs/config/` - Core configuration management (models, loader, validator, legacy)
- `libs/logging/` - Simple Loguru-based logging system
- `config/` - Configuration files (base.yaml, profiles/)
- `tests/config/` - Basic tests for configuration system

## Basic Configuration

### 1. Environment Variables

Create a `.env` file in your project root:

```env
# Application Settings
SYNHOME_ENVIRONMENT=development
SYNHOME_DEBUG=true
SYNHOME_HOST=0.0.0.0
SYNHOME_PORT=8000

# Logging
SYNHOME_LOGGING__LEVEL=INFO
SYNHOME_LOGGING__FILE_PATH=logs/app.log
SYNHOME_LOGGING__MAX_SIZE=100 MB
SYNHOME_LOGGING__RETENTION=30 days

# ZhipuAI (Optional)
SYNHOME_ZHIPUAI__ENABLED=true
SYNHOME_ZHIPUAI__API_KEY=your_api_key_here
SYNHOME_ZHIPUAI__MODEL=chatglm-turbo

# Hot Reload
SYNHOME_HOT_RELOAD__ENABLED=true
SYNHOME_HOT_RELOAD__DEBOUNCE_SECONDS=1.0
```

### 2. Configuration Files

Create base configuration in `config/base.yaml`:

```yaml
# Base Configuration
environment: development
debug: false
host: "0.0.0.0"
port: 8000

# Logging Configuration
logging:
  level: "INFO"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
  file_path: "logs/app.log"
  max_size: "100 MB"
  retention: "30 days"
  compression: "zip"
  rotation: "1 day"
  serialize: false
  enqueue: true

# Hot Reload Configuration
hot_reload:
  enabled: true
  watch_files: ["*.yaml", "*.yml", "*.json"]
  debounce_seconds: 1.0
  reloadable_sections: ["logging", "zhipuai", "device_groups", "scenes"]

# Feature Flags
features:
  enhanced_logging: true
  advanced_validation: true
  metrics_collection: true
```

## Logging Setup

### 1. Basic Loguru Integration

Create `libs/logging/__init__.py`:

```python
from loguru import logger
import sys
from pathlib import Path

def setup_logging(config):
    """Setup Loguru logging based on configuration"""
    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stderr,
        format=config.format,
        level=config.level,
        enqueue=config.enqueue
    )

    # File handler (if configured)
    if config.file_path:
        log_path = Path(config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_path,
            format=config.format,
            level=config.level,
            rotation=config.rotation,
            retention=config.retention,
            compression=config.compression,
            serialize=config.serialize,
            enqueue=config.enqueue
        )

    logger.info("Logging system initialized")
    return logger

# Example usage in your application
# from libs.logging import setup_logging
# logger = setup_logging(config.logging)
```

### 2. Structured Logging

```python
from loguru import logger

# Basic logging
logger.info("Application started")
logger.error("An error occurred", exc_info=True)

# Contextual logging
logger.bind(user_id="admin", device_id="thermostat1").info("Device status updated")

# Lazy evaluation for expensive operations
logger.opt(lazy=True).debug("Expensive data: {}", lambda: calculate_expensive_data())

# Structured logging with JSON
logger.configure(handlers=[
    {
        "sink": "logs/structured.jsonl",
        "format": "{time} | {level} | {message}",
        "serialize": True,
        "enqueue": True
    }
])
```

## Environment Management

### 1. Environment-Specific Configurations

Create `config/profiles/development.yaml`:

```yaml
# Development Environment
environment: development
debug: true

logging:
  level: "DEBUG"
  serialize: false

features:
  enhanced_logging: true
  debug_mode: true
  mock_external_services: true
```

Create `config/profiles/production.yaml`:

```yaml
# Production Environment
environment: production
debug: false

logging:
  level: "INFO"
  serialize: true
  file_path: "/var/log/synhome/app.log"

features:
  enhanced_logging: true
  debug_mode: false
  metrics_collection: true
  security_logging: true
```

### 2. Simplified Configuration Loading

Use the simplified configuration system:

```python
# Basic usage
from libs.config import load_config, AppSettings
from libs.logging import setup_logging, get_logger

# Load configuration with optional overrides
config = load_config(
    config_file="config/demo.yaml",
    debug=True  # Optional override
)

# Setup logging
setup_logging(
    console_output=True,
    file_path="logs/app.log",
    log_level="DEBUG" if config.debug else "INFO"
)

# Get logger
logger = get_logger("my_app")
logger.info("Application started successfully")
```

The simplified system provides:
- **Automatic validation** with Pydantic models
- **Environment variable support** with proper naming conventions
- **Legacy format migration** for backward compatibility
- **Profile-based configuration** for different environments

## FastAPI Integration

### 1. Simplified FastAPI Setup

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from libs.config import load_config, AppSettings
from libs.logging import setup_logging, get_logger
from libs.devices.device_manager import DeviceManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Simple application lifespan for SynHome"""
    global app_settings, device_manager, logger

    try:
        # Load configuration
        config_file = os.getenv("SYNHOME_CONFIG_FILE", "config/demo.yaml")
        debug_mode = os.getenv("SYNHOME_DEBUG", "false").lower() == "true"

        app_settings = load_config(
            config_file=config_file,
            debug=debug_mode
        )

        # Setup logging
        logger = get_logger("synhome_app")
        setup_logging(
            console_output=True,
            file_path="logs/app.log",
            log_level="DEBUG" if app_settings.debug else "INFO"
        )
        logger.info("Logging system initialized")

        # Initialize device manager
        device_manager = DeviceManager()

        # Load devices from configuration
        if hasattr(app_settings, 'devices') and app_settings.devices:
            devices_config = [device.model_dump() for device in app_settings.devices]
            device_manager.load_devices_from_config(devices_config)
            logger.info(f"Loaded {len(device_manager.get_all_devices())} devices")

        # Store in app state
        app.state.app_settings = app_settings
        app.state.device_manager = device_manager

        logger.info(f"SynHome application started successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        logger.info("SynHome application stopped")

app = FastAPI(
    title="SynHome API",
    description="Simplified Smart Home Control System",
    version="1.0.0",
    lifespan=lifespan
)
```

## API Usage

### 1. Get Current Configuration

```bash
curl -X GET "http://localhost:8000/api/v1/config" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Update Configuration

```bash
curl -X PUT "http://localhost:8000/api/v1/config" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "logging": {
      "level": "DEBUG",
      "serialize": true
    }
  }'
```

### 3. Validate Configuration

```bash
curl -X POST "http://localhost:8000/api/v1/config/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "production",
    "logging": {
      "level": "INFO"
    }
  }'
```

### 4. Get Application Status

```bash
curl -X GET "http://localhost:8000/api/v1/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Integration Examples

### 1. Simple Device Manager Integration

```python
from libs.config import load_config, AppSettings
from libs.logging import setup_logging, get_logger
from loguru import logger

class SimpleDeviceManager:
    def __init__(self, config: AppSettings):
        self.config = config
        self.logger = logger.bind(component="DeviceManager")

    async def initialize(self):
        """Initialize devices from configuration"""
        self.logger.info("Initializing device manager")

        # Load device configurations
        if hasattr(self.config, 'devices') and self.config.devices:
            for device_config in self.config.devices:
                await self._load_device(device_config)

            self.logger.info(f"Initialized {len(self.config.devices)} devices")

    async def _load_device(self, device_config):
        """Load individual device"""
        device_logger = self.logger.bind(
            device_id=device_config.id,
            device_type=device_config.type
        )

        try:
            device_logger.info("Loading device")
            # Device loading logic here
            device_logger.success("Device loaded successfully")
        except Exception as e:
            device_logger.error(f"Failed to load device: {e}")
            raise

# Usage
config = load_config()
logger = get_logger("app")
setup_logging(
    console_output=True,
    file_path="logs/app.log",
    log_level="DEBUG" if config.debug else "INFO"
)

device_manager = SimpleDeviceManager(config)
await device_manager.initialize()
```

## Testing

### 1. Basic Configuration Tests

Create simple tests in `tests/config/test_basic.py`:

```python
import pytest
from libs.config import load_config, validate_config
from libs.logging import setup_logging, get_logger

def test_basic_config_loading():
    """Test basic configuration loading"""
    config = load_config()
    assert config is not None
    assert hasattr(config, 'environment')
    assert hasattr(config, 'debug')

def test_config_validation():
    """Test configuration validation"""
    config = load_config()
    is_valid, errors = validate_config(config)
    assert is_valid, f"Configuration validation failed: {errors}"

def test_logging_setup():
    """Test logging setup"""
    logger = get_logger("test")
    assert logger is not None

    # Test logging functionality
    logger.info("Test log message")
```

Run tests with:
```bash
pytest tests/config/test_basic.py -v
```

## Troubleshooting

### Common Issues

#### 1. Configuration Validation Errors

**Problem**: Pydantic validation errors on startup

**Solution**:
```bash
# Check configuration syntax
python -c "
from libs.config import SynHomeConfig
try:
    config = SynHomeConfig()
    print('Configuration is valid')
except Exception as e:
    print(f'Configuration error: {e}')
"
```

#### 2. Logging File Permissions

**Problem**: Cannot write to log files

**Solution**:
```bash
# Create log directory with proper permissions
mkdir -p logs
chmod 755 logs
```

#### 3. Environment Variables Not Loading

**Problem**: Environment variables ignored

**Solution**:
```bash
# Check environment variable loading
uv run python -c "
from libs.config import load_config
config = load_config()
print(f'Environment: {config.environment}')
print(f'Debug: {config.debug}')
"
```

### Debug Mode

Enable debug mode for detailed logging:

```env
SYNHOME_DEBUG=true
SYNHOME_LOGGING__LEVEL=DEBUG
```

## Migration from Legacy Format

The simplified system includes automatic migration from legacy configuration formats:

```python
from libs.config.legacy import migrate_config_file

# Migrate legacy configuration
migrate_config_file(
    old_config_path="config/legacy.yaml",
    new_config_path="config/demo.yaml"
)

print("Legacy configuration migrated successfully")
```

## Next Steps

1. **Run basic tests**: `pytest tests/config/test_basic.py -v`
2. **Review the data model specification**: `data-model.md`
3. **Check the research findings**: `research.md`
4. **Start your FastAPI application**: `uv run python apps/demo/app.py`

## Summary of Simplifications

The simplified system provides:
- **Reduced complexity**: From 55 validation checks to essential core functionality
- **Streamlined API**: Simple `load_config()` function instead of complex class hierarchy
- **Basic logging**: Loguru-based setup without complex formatters or handlers
- **Core validation**: Essential configuration validation without over-engineering
- **Backward compatibility**: Legacy format migration preserved

## Support

For questions or issues:
1. Check the troubleshooting section above
2. Review the simplified code in `libs/config/` and `libs/logging/`
3. Consult the data models for configuration options
4. Test with the provided basic test suite