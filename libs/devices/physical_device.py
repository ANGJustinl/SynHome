#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Physical device implementation with hardware control support
"""

import logging
from typing import Dict, Any, Optional
from .smart_device import SmartDevice, CapabilityType

logger = logging.getLogger(__name__)

class PhysicalDevice(SmartDevice):
    """Physical device implementation that controls real hardware"""
    
    def __init__(self, device_id: str, config: Dict[str, Any]):
        super().__init__(device_id, config)
        
        # Hardware connection parameters
        self.connection_config = config.get("connection", {})
        self.connection_type = self.connection_config.get("type", "")
        self.connection = None
        
        # Initialize hardware connection based on type
        self._init_connection()
        
    def _init_connection(self):
        """Initialize connection to physical device"""
        try:
            if self.connection_type == "serial":
                self._init_serial_connection()
            elif self.connection_type == "gpio":
                self._init_gpio_connection()
            elif self.connection_type == "modbus":
                self._init_modbus_connection()
            elif self.connection_type == "zigbee":
                self._init_zigbee_connection()
            else:
                logger.error(f"Unsupported connection type: {self.connection_type}")
        except Exception as e:
            logger.error(f"Failed to initialize connection: {str(e)}")

    def _init_serial_connection(self):
        """Initialize serial connection"""
        try:
            import serial
            port = self.connection_config.get("port", "")
            baudrate = self.connection_config.get("baudrate", 9600)
            self.connection = serial.Serial(port, baudrate)
            logger.info(f"Serial connection established on {port}")
        except Exception as e:
            logger.error(f"Failed to initialize serial connection: {str(e)}")

    def _init_gpio_connection(self):
        """Initialize GPIO connection"""
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            self.connection = GPIO
            pins = self.connection_config.get("pins", {})
            for pin_name, pin_number in pins.items():
                GPIO.setup(pin_number, GPIO.OUT)
            logger.info("GPIO connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GPIO connection: {str(e)}")

    def _init_modbus_connection(self):
        """Initialize Modbus connection"""
        try:
            from pymodbus.client import ModbusSerialClient, ModbusTcpClient
            
            mode = self.connection_config.get("mode", "tcp")
            if mode == "tcp":
                host = self.connection_config.get("host", "localhost")
                port = self.connection_config.get("port", 502)
                self.connection = ModbusTcpClient(host, port)
            else:  # RTU mode
                port = self.connection_config.get("port", "")
                baudrate = self.connection_config.get("baudrate", 9600)
                self.connection = ModbusSerialClient(
                    method="rtu",
                    port=port,
                    baudrate=baudrate
                )
            logger.info(f"Modbus connection established in {mode} mode")
        except Exception as e:
            logger.error(f"Failed to initialize Modbus connection: {str(e)}")

    def _init_zigbee_connection(self):
        """Initialize Zigbee connection"""
        try:
            from zigpy.application import ControllerApplication
            from zigpy_zigate import ZiGate
            
            port = self.connection_config.get("port", "")
            self.connection = ZiGate(port)
            logger.info(f"Zigbee connection established on {port}")
        except Exception as e:
            logger.error(f"Failed to initialize Zigbee connection: {str(e)}")

    def set_capability(self, name: str, value: Any) -> bool:
        """Set capability value and control physical device"""
        if not super().set_capability(name, value):
            return False
            
        return self._send_hardware_command(name, value)
        
    def _send_hardware_command(self, capability: str, value: Any) -> bool:
        """Send command to physical hardware"""
        try:
            if not self.connection:
                logger.error("No hardware connection available")
                return False
                
            # Get capability configuration
            cap = self.capabilities[capability]
            
            if self.connection_type == "serial":
                return self._send_serial_command(capability, value, cap)
            elif self.connection_type == "gpio":
                return self._send_gpio_command(capability, value, cap)
            elif self.connection_type == "modbus":
                return self._send_modbus_command(capability, value, cap)
            elif self.connection_type == "zigbee":
                return self._send_zigbee_command(capability, value, cap)
            else:
                logger.error(f"Unsupported connection type: {self.connection_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending hardware command: {str(e)}")
            return False

    def _send_serial_command(self, capability: str, value: Any, cap_config) -> bool:
        """Send command via serial connection"""
        try:
            # Format command based on protocol
            protocol = self.connection_config.get("protocol", "text")
            
            if protocol == "text":
                # Simple text protocol: "SET capability value"
                command = f"SET {capability} {value}\n"
                self.connection.write(command.encode())
            else:
                # Binary protocol
                command = self._format_binary_command(capability, value)
                self.connection.write(command)
                
            return True
        except Exception as e:
            logger.error(f"Serial command error: {str(e)}")
            return False

    def _send_gpio_command(self, capability: str, value: Any, cap_config) -> bool:
        """Send command via GPIO"""
        try:
            pins = self.connection_config.get("pins", {})
            if capability not in pins:
                logger.error(f"No GPIO pin configured for {capability}")
                return False
                
            pin = pins[capability]
            
            if cap_config.type == CapabilityType.SWITCH:
                # Convert on/off to GPIO high/low
                gpio_value = 1 if value == "on" else 0
                self.connection.output(pin, gpio_value)
            elif cap_config.type == CapabilityType.NUMBER:
                # Use PWM for number values
                if not hasattr(self, f"pwm_{pin}"):
                    self.connection.setup(pin, self.connection.OUT)
                    freq = self.connection_config.get("pwm_frequency", 1000)
                    setattr(self, f"pwm_{pin}", 
                           self.connection.PWM(pin, freq))
                    getattr(self, f"pwm_{pin}").start(0)
                    
                # Convert value to duty cycle (0-100)
                duty_cycle = (value - cap_config.min_value) / (
                    cap_config.max_value - cap_config.min_value) * 100
                getattr(self, f"pwm_{pin}").ChangeDutyCycle(duty_cycle)
                
            return True
        except Exception as e:
            logger.error(f"GPIO command error: {str(e)}")
            return False

    def _send_modbus_command(self, capability: str, value: Any, cap_config) -> bool:
        """Send command via Modbus"""
        try:
            # Get Modbus register configuration
            registers = self.connection_config.get("registers", {})
            if capability not in registers:
                logger.error(f"No Modbus register configured for {capability}")
                return False
                
            reg_config = registers[capability]
            reg_addr = reg_config.get("address")
            reg_type = reg_config.get("type", "holding")
            
            # Convert value based on capability type
            if cap_config.type == CapabilityType.SWITCH:
                reg_value = 1 if value == "on" else 0
            elif cap_config.type == CapabilityType.NUMBER:
                # Scale value to register range if specified
                scale = reg_config.get("scale", 1)
                reg_value = int(float(value) * scale)
            else:  # ENUM
                # Map enum values to register values
                value_map = reg_config.get("value_map", {})
                reg_value = value_map.get(value, 0)
                
            # Write to appropriate register type
            if reg_type == "holding":
                self.connection.write_register(reg_addr, reg_value)
            elif reg_type == "coil":
                self.connection.write_coil(reg_addr, reg_value)
                
            return True
        except Exception as e:
            logger.error(f"Modbus command error: {str(e)}")
            return False

    def _send_zigbee_command(self, capability: str, value: Any, cap_config) -> bool:
        """Send command via Zigbee"""
        try:
            # Get Zigbee endpoint configuration
            endpoints = self.connection_config.get("endpoints", {})
            if capability not in endpoints:
                logger.error(f"No Zigbee endpoint configured for {capability}")
                return False
                
            ep_config = endpoints[capability]
            endpoint = ep_config.get("endpoint")
            cluster = ep_config.get("cluster")
            attribute = ep_config.get("attribute")
            
            # Convert value based on capability type
            if cap_config.type == CapabilityType.SWITCH:
                zigbee_value = 1 if value == "on" else 0
            elif cap_config.type == CapabilityType.NUMBER:
                # Scale value if needed
                scale = ep_config.get("scale", 1)
                zigbee_value = int(float(value) * scale)
            else:  # ENUM
                # Map enum values to Zigbee values
                value_map = ep_config.get("value_map", {})
                zigbee_value = value_map.get(value, 0)
                
            # Write attribute to device
            self.connection.devices[endpoint].write_attributes(
                cluster,
                {attribute: zigbee_value}
            )
            
            return True
        except Exception as e:
            logger.error(f"Zigbee command error: {str(e)}")
            return False

    def _format_binary_command(self, capability: str, value: Any) -> bytes:
        """Format binary command based on protocol specification"""
        protocol = self.connection_config.get("protocol", {})
        start_byte = protocol.get("start_byte", 0xAA)
        end_byte = protocol.get("end_byte", 0xFF)
        
        # Get command code for capability
        cmd_codes = protocol.get("command_codes", {})
        cmd_code = cmd_codes.get(capability, 0x00)
        
        # Format value based on capability type
        cap = self.capabilities[capability]
        if cap.type == CapabilityType.SWITCH:
            val_byte = 0x01 if value == "on" else 0x00
        elif cap.type == CapabilityType.NUMBER:
            # Scale value to 0-255 range
            scaled = int((value - cap.min_value) / (
                cap.max_value - cap.min_value) * 255)
            val_byte = max(0, min(255, scaled))
        else:  # ENUM
            # Map enum values to codes
            val_codes = protocol.get("value_codes", {}).get(capability, {})
            val_byte = val_codes.get(value, 0x00)
            
        # Assemble command bytes
        cmd_bytes = bytes([
            start_byte,
            cmd_code,
            val_byte,
            end_byte
        ])
        
        return cmd_bytes
        
    def close(self):
        """Clean up hardware connection"""
        try:
            if self.connection:
                if self.connection_type == "serial":
                    self.connection.close()
                elif self.connection_type == "gpio":
                    self.connection.cleanup()
                elif self.connection_type == "modbus":
                    self.connection.close()
                elif self.connection_type == "zigbee":
                    self.connection.close()
                    
            logger.info(f"Closed {self.connection_type} connection")
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")