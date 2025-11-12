# Data Model Design: SynHome Configuration and Logging

**Date**: 2025-11-12
**Scope**: Core data models for configuration management, logging, and hot reload functionality

## Overview

This document defines the core data models for the SynHome configuration and logging optimization feature. The design maintains compatibility with existing device configurations while introducing type-safe validation and structured logging.

## Core Configuration Models

### 1. Application Settings Model

```python
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum

class Environment(str, Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogConfig(BaseModel):
    """Logging configuration"""
    level: LogLevel = LogLevel.INFO
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    file_path: Optional[str] = None
    max_size: str = "100 MB"
    retention: str = "30 days"
    compression: str = "zip"
    rotation: str = "1 day"
    serialize: bool = False
    enqueue: bool = True

    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        return LogLevel(v.upper())

class ZhipuAIConfig(BaseModel):
    """ZhipuAI LLM configuration"""
    enabled: bool = False
    api_key: str = Field(description="ZhipuAI API key")
    model: str = "chatglm-turbo"
    timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError('API key must be at least 10 characters long')
        return v

class HotReloadConfig(BaseModel):
    """Hot reload configuration"""
    enabled: bool = True
    watch_files: List[str] = Field(default_factory=lambda: ["*.yaml", "*.yml"])
    debounce_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
    reloadable_sections: List[str] = Field(
        default_factory=lambda: ["logging", "zhipuai", "device_groups", "scenes"]
    )

class AppSettings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_prefix="SYNHOME_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid"
    )

    # Core settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    # Logging
    logging: LogConfig = LogConfig()

    # LLM Integration
    zhipuai: Optional[ZhipuAIConfig] = None

    # Hot Reload
    hot_reload: HotReloadConfig = HotReloadConfig()

    # Feature Flags
    features: Dict[str, bool] = Field(default_factory=dict)
```

### 2. Device Configuration Models

```python
from typing import Union, Literal
from enum import Enum

class CapabilityType(str, Enum):
    """Device capability types"""
    SWITCH = "switch"
    NUMBER = "number"
    ENUM = "enum"

class CapabilityConfig(BaseModel):
    """Device capability configuration"""
    type: CapabilityType
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: Optional[str] = None
    values: Optional[List[str]] = None
    states: Optional[List[str]] = None
    current_value: Optional[Union[str, int, float, bool]] = None

    @field_validator('min_value', 'max_value')
    @classmethod
    def validate_numeric_range(cls, v, info):
        if info.field_name == 'max_value' and v is not None:
            # This will be validated in model_validator
            pass
        return v

    @model_validator(mode='after')
    def validate_capability_consistency(self):
        if self.type == CapabilityType.NUMBER:
            if self.min_value is None or self.max_value is None:
                raise ValueError("Number capability must have min_value and max_value")
            if self.min_value >= self.max_value:
                raise ValueError("min_value must be less than max_value")

        elif self.type == CapabilityType.ENUM:
            if not self.values or len(self.values) == 0:
                raise ValueError("Enum capability must have values")

        elif self.type == CapabilityType.SWITCH:
            if not self.states or len(self.states) != 2:
                raise ValueError("Switch capability must have exactly 2 states")

        return self

class DeviceConfig(BaseModel):
    """Device configuration"""
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(pattern=r'^[a-z_]+$')
    capabilities: Dict[str, CapabilityConfig]
    enabled: bool = True
    tags: List[str] = Field(default_factory=list)
    adapter_id: Optional[str] = None

    @field_validator('id')
    @classmethod
    def validate_device_id(cls, v):
        if not v.strip():
            raise ValueError('Device ID cannot be empty')
        return v.strip()

class AdapterConfig(BaseModel):
    """Communication adapter configuration"""
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    type: Literal["websocket", "mqtt", "http", "serial", "modbus", "zigbee", "gpio"]
    config: Dict[str, Any]
    enabled: bool = True
    timeout: int = Field(default=30, ge=1, le=300)

    @field_validator('config')
    @classmethod
    def validate_adapter_specific_config(cls, v, info):
        adapter_type = info.data.get('type')

        if adapter_type == "websocket":
            required_fields = ["url"]
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"WebSocket adapter requires '{field}' in config")

        elif adapter_type == "mqtt":
            required_fields = ["host"]
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"MQTT adapter requires '{field}' in config")

        return v

class SmartHomeConfig(BaseModel):
    """Complete smart home configuration"""
    devices: List[DeviceConfig] = Field(default_factory=list)
    adapters: List[AdapterConfig] = Field(default_factory=list)
    device_groups: List[Dict[str, Any]] = Field(default_factory=list)
    scenes: List[Dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_references(self):
        device_ids = {device.id for device in self.devices}
        adapter_ids = {adapter.id for adapter in self.adapters}

        # Validate adapter references in devices
        for device in self.devices:
            if device.adapter_id and device.adapter_id not in adapter_ids:
                raise ValueError(f"Device {device.id} references non-existent adapter: {device.adapter_id}")

        # Validate scene device references
        for scene in self.scenes:
            for action in scene.get('actions', []):
                device_id = action.get('device_id')
                if device_id != "ALL" and device_id not in device_ids:
                    raise ValueError(f"Scene references non-existent device: {device_id}")

        # Validate device group references
        for group in self.device_groups:
            for device_id in group.get('devices', []):
                if device_id not in device_ids:
                    raise ValueError(f"Device group references non-existent device: {device_id}")

        return self
```

## Logging Data Models

### 1. Log Entry Model

```python
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class LogContext(BaseModel):
    """Structured log context"""
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

class LogEntry(BaseModel):
    """Structured log entry"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str
    logger_name: str
    message: str
    context: LogContext = Field(default_factory=LogContext)
    exception: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class LogFilter(BaseModel):
    """Log filter configuration"""
    level: Optional[str] = None
    logger_name: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    time_range: Optional[Dict[str, datetime]] = None
```

### 2. Log Metrics Model

```python
from typing import Dict, List

class LogMetrics(BaseModel):
    """Logging performance metrics"""
    total_entries: int = 0
    entries_by_level: Dict[str, int] = Field(default_factory=dict)
    entries_per_second: float = 0.0
    average_size_bytes: float = 0.0
    error_rate: float = 0.0
    last_entry: Optional[datetime] = None

class LogSinkMetrics(BaseModel):
    """Individual log sink metrics"""
    name: str
    type: str  # file, console, etc.
    entries_written: int = 0
    bytes_written: int = 0
    errors: int = 0
    last_write: Optional[datetime] = None
    is_healthy: bool = True
```

## Hot Reload Models

### 1. Configuration Change Model

```python
from enum import Enum
from typing import Optional

class ChangeType(str, Enum):
    """Types of configuration changes"""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"

class ConfigChange(BaseModel):
    """Configuration change record"""
    file_path: str
    change_type: ChangeType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    affected_sections: List[str] = Field(default_factory=list)
    reloadable: bool = True
    validation_status: Optional[str] = None
    error_message: Optional[str] = None

class ReloadResult(BaseModel):
    """Configuration reload result"""
    success: bool
    changes_applied: List[ConfigChange] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    rollback_performed: bool = False
    processing_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 2. Configuration State Model

```python
class ConfigurationState(BaseModel):
    """Current configuration state"""
    config_hash: str
    last_reload: Optional[datetime] = None
    reload_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    monitored_files: List[str] = Field(default_factory=list)
    hot_reload_enabled: bool = True

    def is_healthy(self) -> bool:
        """Check if configuration state is healthy"""
        return self.error_count < 5 and self.last_error is None
```

## Validation Models

### 1. Configuration Validation

```python
class ValidationRule(BaseModel):
    """Configuration validation rule"""
    name: str
    description: str
    field_path: str  # dot notation for nested fields
    rule_type: str  # required, type_check, range, pattern, etc.
    parameters: Dict[str, Any] = Field(default_factory=dict)
    error_message: str

class ValidationResult(BaseModel):
    """Configuration validation result"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validated_fields: List[str] = Field(default_factory=list)
    validation_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

## Environment Configuration Models

### 1. Environment-Specific Settings

```python
class DatabaseConfig(BaseModel):
    """Database configuration"""
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    name: str
    username: str
    password: str
    ssl: bool = True
    pool_size: int = Field(default=10, ge=1, le=100)

class RedisConfig(BaseModel):
    """Redis configuration"""
    host: str = "localhost"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)
    password: Optional[str] = None
    ssl: bool = False
    max_connections: int = Field(default=20, ge=1, le=100)

class EnvironmentConfig(BaseModel):
    """Environment-specific configuration"""
    name: Environment
    database: Optional[DatabaseConfig] = None
    redis: Optional[RedisConfig] = None
    logging: LogConfig = LogConfig()
    debug: bool = False
    features: Dict[str, bool] = Field(default_factory=dict)
```

## Model Relationships

### Configuration Hierarchy

```
AppSettings (Root)
├── EnvironmentConfig
│   ├── DatabaseConfig
│   ├── RedisConfig
│   └── LogConfig
├── SmartHomeConfig
│   ├── DeviceConfig[]
│   │   └── CapabilityConfig[]
│   ├── AdapterConfig[]
│   ├── DeviceGroup[]
│   └── Scene[]
├── ZhipuAIConfig
└── HotReloadConfig
```

### Data Flow

1. **Loading**: Environment variables → YAML files → Pydantic models
2. **Validation**: Field validators → Model validators → Custom rules
3. **Usage**: Type-safe access → Automatic serialization → Error handling
4. **Hot Reload**: File changes → Validation → Atomic updates → Rollback on failure

## Migration Compatibility

### Backward Compatibility Layer

```python
class LegacyConfigAdapter(BaseModel):
    """Adapter for legacy configuration formats"""

    @classmethod
    def from_demo_yaml(cls, yaml_data: Dict[str, Any]) -> SmartHomeConfig:
        """Convert existing demo.yaml format to new models"""
        devices = []
        for device_data in yaml_data.get('devices', []):
            # Transform legacy format to new DeviceConfig
            capabilities = {}
            for cap_name, cap_config in device_data.get('capabilities', {}).items():
                capabilities[cap_name] = CapabilityConfig(**cap_config)

            devices.append(DeviceConfig(
                id=device_data['id'],
                name=device_data['name'],
                type=device_data['type'],
                capabilities=capabilities,
                enabled=device_data.get('enabled', True)
            ))

        return SmartHomeConfig(devices=devices)
```

This data model design provides a robust foundation for the configuration and logging optimization while maintaining full compatibility with existing SynHome configurations.