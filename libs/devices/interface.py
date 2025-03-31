#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device interfaces and common types
"""

from enum import Enum, auto
from typing import List

class DeviceType(Enum):
    """Device type enumeration"""
    THERMOSTAT = "thermostat"
    LIGHT = "light"
    RICE_COOKER = "rice_cooker"

class DeviceState(Enum):
    """Device state enumeration"""
    IDLE = "IDLE"
    ON = "ON"
    OFF = "OFF"
    RUNNING = "RUNNING"

class DeviceCapability(Enum):
    """Device capability enumeration"""
    SWITCHABLE = "switchable"
    DIMMABLE = "dimmable"
    COLOR = "color"
    TEMPERATURE = "temperature"
    LLM_CONTROL = "llm_control"
    PROGRAMMABLE = "programmable"
    ENERGY_MONITORING = "energy_monitoring"
    TIMED_OPERATION = "timed_operation"

class BaseDevice:
    """Base device interface"""
    def __init__(self, device_id: str, name: str, device_type: DeviceType):
        self.id = device_id
        self.name = name
        self.type = device_type
        self.state = DeviceState.IDLE
        self.capabilities: List[DeviceCapability] = []
        self.attributes = {}

    def enable_llm_control(self, api_key: str):
        """Enable LLM control capability"""
        self.capabilities.append(DeviceCapability.LLM_CONTROL)

    def process_natural_command(self, command: str) -> bool:
        """Process natural language command"""
        raise NotImplementedError("Subclass must implement abstract method")

    def update_state(self, new_state: DeviceState):
        """Update device state"""
        self.state = new_state
