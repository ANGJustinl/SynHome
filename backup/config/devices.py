"""
Device configuration models for SynHome.

These models define the structure for device configurations, capabilities,
and adapter settings while maintaining backward compatibility with existing formats.
"""

from typing import Dict, Any, List, Union, Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


class CapabilityType(str, Enum):
    """Device capability types."""
    SWITCH = "switch"
    NUMBER = "number"
    ENUM = "enum"


class CapabilityConfig(BaseModel):
    """Device capability configuration."""
    type: CapabilityType
    min_value: Optional[float] = Field(
        default=None,
        description="Minimum value for numeric capabilities"
    )
    max_value: Optional[float] = Field(
        default=None,
        description="Maximum value for numeric capabilities"
    )
    unit: Optional[str] = Field(
        default=None,
        description="Unit of measurement for numeric capabilities"
    )
    values: Optional[List[str]] = Field(
        default=None,
        description="Possible values for enum capabilities"
    )
    states: Optional[List[str]] = Field(
        default=None,
        description="Possible states for switch capabilities"
    )
    current_value: Optional[Union[str, int, float, bool]] = Field(
        default=None,
        description="Current value of the capability"
    )

    @model_validator(mode='after')
    def validate_capability_consistency(self):
        """Validate capability configuration consistency."""
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
    """Device configuration model."""
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

    @field_validator('name')
    @classmethod
    def validate_device_name(cls, v):
        if not v.strip():
            raise ValueError('Device name cannot be empty')
        return v.strip()


class AdapterConfig(BaseModel):
    """Communication adapter configuration model."""
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    type: Literal[
        "websocket", "mqtt", "http", "serial", "modbus", "zigbee", "gpio"
    ]
    config: Dict[str, Any]
    enabled: bool = True
    timeout: int = Field(default=30, ge=1, le=300)

    @field_validator('config')
    @classmethod
    def validate_adapter_specific_config(cls, v, info):
        """Validate adapter-specific configuration."""
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


class DeviceGroupModel(BaseModel):
    """Device group model."""
    id: str
    name: str
    devices: List[str] = Field(description="Device ID list")
    description: Optional[str] = None

    @field_validator('devices')
    @classmethod
    def validate_devices(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("Device group cannot have duplicate devices")
        return v


class SceneAction(BaseModel):
    """Scene action model."""
    device_id: str
    command: str
    params: Dict[str, Any] = Field(default_factory=dict)


class SceneModel(BaseModel):
    """Scene model."""
    id: str
    name: str
    description: Optional[str] = None
    actions: List[SceneAction]
    enabled: bool = True

    @field_validator('actions')
    @classmethod
    def validate_actions(cls, v):
        if not v:
            raise ValueError("Scene must contain at least one action")
        return v


class SmartHomeConfig(BaseModel):
    """Complete smart home configuration model."""
    devices: List[DeviceConfig] = Field(default_factory=list)
    adapters: List[AdapterConfig] = Field(default_factory=list)
    device_groups: List[DeviceGroupModel] = Field(default_factory=list)
    scenes: List[SceneModel] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_references(self):
        """Validate all cross-references in the configuration."""
        device_ids = {device.id for device in self.devices}
        adapter_ids = {adapter.id for adapter in self.adapters}

        # Validate adapter references in devices
        for device in self.devices:
            if device.adapter_id and device.adapter_id not in adapter_ids:
                raise ValueError(
                    f"Device {device.id} references non-existent adapter: {device.adapter_id}"
                )

        # Validate scene device references
        for scene in self.scenes:
            for action in scene.actions:
                device_id = action.device_id
                if device_id != "ALL" and device_id not in device_ids:
                    raise ValueError(
                        f"Scene {scene.id} references non-existent device: {device_id}"
                    )

        # Validate device group references
        for group in self.device_groups:
            for device_id in group.devices:
                if device_id not in device_ids:
                    raise ValueError(
                        f"Device group {group.id} references non-existent device: {device_id}"
                    )

        return self

    def get_device_by_id(self, device_id: str) -> Optional[DeviceConfig]:
        """Get device configuration by ID."""
        for device in self.devices:
            if device.id == device_id:
                return device
        return None

    def get_adapter_by_id(self, adapter_id: str) -> Optional[AdapterConfig]:
        """Get adapter configuration by ID."""
        for adapter in self.adapters:
            if adapter.id == adapter_id:
                return adapter
        return None

    def get_enabled_devices(self) -> List[DeviceConfig]:
        """Get all enabled devices."""
        return [device for device in self.devices if device.enabled]

    def get_enabled_adapters(self) -> List[AdapterConfig]:
        """Get all enabled adapters."""
        return [adapter for adapter in self.adapters if adapter.enabled]