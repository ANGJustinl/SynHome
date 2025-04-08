#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device manager for creating and managing smart devices
"""

import logging
from typing import Dict, List, Any, Optional
from .smart_device import SmartDevice, Capability, CapabilityType
from ..utils.llm import ZhipuAIClient
from ..utils.command_parser import CommandParser
from ..adapters import get_adapter_class, DeviceAdapter

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manager for smart devices"""
    
    def __init__(self):
        """Initialize device manager"""
        self.devices: Dict[str, SmartDevice] = {}
        self.llm_client: Optional[ZhipuAIClient] = None
        self.adapters: Dict[str, DeviceAdapter] = {}  # 设备适配器
        
    def load_devices_from_config(self, devices_config: List[Dict[str, Any]]):
        """
        Load devices from configuration
        
        Args:
            devices_config: List of device configurations
        """
        for device_config in devices_config:
            try:
                device = self._create_device_from_config(device_config)
                if device:
                    self.devices[device.id] = device
                    logger.info(f"Created device {device.id} ({device.name})")
            except Exception as e:
                logger.error(f"Error creating device from config: {str(e)}")
    
    def _create_device_from_config(self, config: Dict[str, Any]) -> Optional[SmartDevice]:
        """
        Create a device from configuration
        
        Args:
            config: Device configuration dictionary
            
        Returns:
            SmartDevice instance if successful, None otherwise
        """
        try:
            device_id = config.get("id")
            device_name = config.get("name")
            device_type = config.get("type")
            
            if not all([device_id, device_name, device_type]):
                logger.error("Missing required device configuration")
                return None
            
            device = SmartDevice(device_id, config)
            return device
            
        except Exception as e:
            logger.error(f"Error creating device: {str(e)}")
            return None
    
    def enable_llm_control(self, api_key: str):
        """
        Enable LLM control for all devices
        
        Args:
            api_key: API key for LLM service
        """
        self.llm_client = ZhipuAIClient(api_key)
        
        for device in self.devices.values():
            device.llm_client = self.llm_client
    
    def get_device_by_id(self, device_id: str) -> Optional[SmartDevice]:
        """Get device by ID"""
        return self.devices.get(device_id)
    
    def get_device_by_type(self, device_type: str) -> Optional[SmartDevice]:
        """Get first device matching the given type"""
        for device in self.devices.values():
            if device.type.lower() == device_type.lower():
                return device
        return None
    
    def get_all_devices(self) -> List[SmartDevice]:
        """Get all devices"""
        return list(self.devices.values())
    
    def process_command(self, command: str, device_hint: str = None) -> Dict[str, Any]:
        """
        Process a natural language command
        
        Args:
            command: Natural language command
            device_hint: Optional hint about which device to control
            
        Returns:
            Dictionary with processing result
        """
        if not self.llm_client:
            return {"success": False, "message": "LLM control not enabled"}
        
        # Add debug logs
        logger.info("Processing command: '%s', device hint: %s", command, device_hint)
        
        try:
            # 检查是否是跨设备多操作命令
            if CommandParser.detect_multi_device_operations(command):
                logger.info("Detected cross-device multi-operation command")
                return self._process_cross_device_command(command)
                
            # 检测命令类型 - 单设备、多设备（同类）、群组或场景
            command_type = CommandParser.detect_command_type(command)
            logger.info("Detected command type: %s", command_type)
            
            if command_type == 'multi_device':
                # 处理针对多个设备的命令（同一类型设备）
                return self._process_multi_device_command(command)
            
            # 处理单设备命令
            target_device = None
            if device_hint:
                target_device = self.get_device_by_id(device_hint) or self.get_device_by_type(device_hint)
            
            if not target_device:
                # 通过LLM确定命令针对哪种设备
                device_type = self._determine_device_type(command)
                logger.info("LLM determined device type: %s", device_type)
                if device_type:
                    target_device = self.get_device_by_type(device_type)
            
            if not target_device:
                logger.warning("Could not determine target device for command: %s", command)
                return {"success": False, "message": "Could not determine target device"}
            
            # 处理单设备命令
            logger.info("Executing command '%s' for device %s", command, target_device.name)
            result = target_device.process_natural_command(command)
            
            return {
                "success": result, 
                "device_id": target_device.id,
                "device_name": target_device.name,
                "message": "Command processed successfully" if result else "Failed to process command"
            }
            
        except Exception as e:
            logger.error("Error processing command: %s", str(e), exc_info=True)
            return {"success": False, "message": f"Error processing command: {str(e)}"}

    def _process_multi_device_command(self, command: str) -> Dict[str, Any]:
        """
        Process a command targeting multiple devices
        
        Args:
            command: Natural language command
            
        Returns:
            Dictionary with processing results
        """
        # Extract device names or use ALL for all devices
        device_names = [device.name for device in self.devices.values()]
        target_devices = CommandParser.extract_devices_from_command(command, device_names)
        
        # If no specific devices found or "ALL" marker is present, target all devices
        if not target_devices or "ALL" in target_devices:
            target_devices = list(self.devices.values())
            logger.info(f"Targeting all devices: {len(target_devices)} devices")
        else:
            # Get actual device objects from names
            target_devices = [device for device in self.devices.values() 
                             if device.name in target_devices]
            device_names_str = ", ".join([d.name for d in target_devices])
            logger.info(f"Targeting specific devices: {device_names_str}")
        
        if not target_devices:
            return {"success": False, "message": "No valid devices found for command"}
        
        # Ask LLM to create a standardized operation for all targeted devices
        operation = self._create_standardized_operation(command)
        if not operation:
            return {"success": False, "message": "Failed to create operation from command"}
        
        # Apply operation to all targeted devices
        results = []
        success_count = 0
        
        for device in target_devices:
            try:
                # Adapt operation to device capabilities if needed
                adapted_operation = self._adapt_operation_to_device(operation, device)
                
                # Execute operation on device
                if adapted_operation:
                    logger.info(f"Applying operation to device {device.name}: {adapted_operation['command']}")
                    result = device.process_natural_command(adapted_operation["command"])
                    results.append({
                        "device_id": device.id,
                        "device_name": device.name,
                        "success": result
                    })
                    if result:
                        success_count += 1
                else:
                    logger.warning(f"Could not adapt operation for device {device.name}")
                    results.append({
                        "device_id": device.id,
                        "device_name": device.name,
                        "success": False,
                        "error": "Could not adapt operation for this device"
                    })
            except Exception as e:
                logger.error(f"Error applying operation to device {device.name}: {str(e)}")
                results.append({
                    "device_id": device.id,
                    "device_name": device.name,
                    "success": False,
                    "error": str(e)
                })
        
        message = f"Command executed successfully on {success_count}/{len(target_devices)} devices"
        logger.info(message)
        
        return {
            "success": success_count > 0,
            "message": message,
            "device_count": len(target_devices),
            "success_count": success_count,
            "results": results
        }

    def _process_cross_device_command(self, command: str) -> Dict[str, Any]:
        """
        处理跨设备多操作命令
        
        Args:
            command: 自然语言命令
            
        Returns:
            处理结果
        """
        # 1. 获取系统中所有可用的设备类型
        device_types = list(set(device.type for device in self.devices.values()))
        
        # 2. 拆分命令为针对不同设备的子命令
        device_commands = CommandParser.split_multi_device_command(command, device_types)
        logger.info(f"Split cross-device command into {len(device_commands)} device-specific commands: {device_commands}")
        
        # 3. 依次执行各设备的子命令
        results = []
        success_count = 0
        device_count = 0
        processed_devices = {}  # 记录已处理的设备，避免重复处理同类型设备
        
        for device_type, sub_command in device_commands.items():
            # 找到该类型的设备
            device = self.get_device_by_type(device_type)
            if not device:
                logger.warning(f"No device found for type: {device_type}")
                continue
                
            if device.id in processed_devices:
                continue  # 跳过已处理的设备
                
            device_count += 1
            processed_devices[device.id] = True
            
            # 执行设备命令
            logger.info(f"Executing sub-command '{sub_command}' for {device_type} device {device.name}")
            result = device.process_natural_command(sub_command)
            
            results.append({
                "device_id": device.id,
                "device_name": device.name,
                "device_type": device_type,
                "command": sub_command,
                "success": result
            })
            
            if result:
                success_count += 1
        
        message = f"Executed {len(device_commands)} sub-commands across {device_count} devices, {success_count} successful."
        logger.info(message)
        
        return {
            "success": success_count > 0,
            "message": message,
            "device_count": device_count,
            "success_count": success_count,
            "sub_commands": len(device_commands),
            "results": results
        }

    def _create_standardized_operation(self, command: str) -> Optional[Dict[str, Any]]:
        """
        Create a standardized operation from natural language command
        
        Args:
            command: Natural language command
            
        Returns:
            Dictionary with standardized operation details
        """
        try:
            # Use LLM to extract core operation from command
            system_prompt = """Extract the core operation from this command that applies to multiple devices.
Format the response as a JSON object with 'operation' and 'parameters' fields.
Example: 'Turn off all lights' -> {"operation": "power_off", "parameters": {}}
Example: 'Set temperature to 25 for all thermostats' -> {"operation": "set_temperature", "parameters": {"temperature": 25}}"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": command}
            ]
            
            response = self.llm_client.chat(messages)
            if not response:
                return None
                
            # Extract JSON operation from response
            import json
            import re
            
            # Find JSON in response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.error("No JSON found in LLM response: %s", response)
                return None
                
            operation = json.loads(json_match.group(0))
            logger.info("Extracted operation: %s", operation)
            return operation
            
        except Exception as e:
            logger.error("Error creating standardized operation: %s", str(e))
            return None

    def _adapt_operation_to_device(self, operation: Dict[str, Any], device: Any) -> Optional[Dict[str, Any]]:
        """
        Adapt a standardized operation to a specific device's capabilities
        
        Args:
            operation: Standardized operation dictionary
            device: Target device object
            
        Returns:
            Adapted operation for the device, or None if not applicable
        """
        op_type = operation.get("operation", "")
        params = operation.get("parameters", {})
        
        # Create device-specific command based on operation type
        if op_type == "power_off":
            return {"command": "turn off"}
        elif op_type == "power_on":
            return {"command": "turn on"}
        elif op_type.startswith("set_"):
            capability = op_type[4:]  # Remove "set_" prefix
            if capability in device.capabilities:
                param_value = params.get(capability)
                if param_value is not None:
                    return {"command": f"set {capability} to {param_value}"}
        
        # If we can't adapt the operation, return None
        logger.warning("Cannot adapt operation %s to device %s", op_type, device.name)
        return None
    
    def _determine_device_type(self, command: str) -> Optional[str]:
        """
        Use LLM to determine which device type the command is referring to
        
        Args:
            command: Natural language command
            
        Returns:
            Device type string if determined, None otherwise
        """
        try:
            # Get all available device types
            available_types = [d.type for d in self.devices.values()]
            
            # Ask LLM to identify the device type from the command
            device_info = {
                "available_types": available_types,
                "command": command
            }
            
            # Use a simplified prompt to determine device type
            system_prompt = """Determine which device type this command is referring to.
Only respond with the device type name from the available types.
If unsure, respond with the most likely device type."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Available device types: {', '.join(available_types)}\nCommand: {command}"}
            ]
            
            response = self.llm_client.chat(messages)
            if response:
                # Extract device type from response
                detected_type = response.lower().strip()
                for device_type in available_types:
                    if device_type.lower() in detected_type:
                        return device_type
            
            return None
            
        except Exception as e:
            logger.error(f"Error determining device type: {str(e)}")
            return None
    
    async def load_adapters_from_config(self, adapters_config: List[Dict[str, Any]]):
        """
        从配置加载设备适配器
        
        Args:
            adapters_config: 适配器配置列表
        """
        for adapter_config in adapters_config:
            try:
                adapter_id = adapter_config["id"]
                adapter_type = adapter_config["type"]
                adapter_class = get_adapter_class(adapter_type)
                
                if not adapter_class:
                    logger.error(f"Unsupported adapter type: {adapter_type}")
                    continue
                    
                # 创建适配器实例
                adapter = adapter_class(adapter_id, adapter_config["config"])
                self.adapters[adapter_id] = adapter
                
                # 注册状态回调
                adapter.register_status_callback(self._on_device_status_update)
                
                # 连接适配器
                connected = await adapter.connect()
                if connected:
                    logger.info(f"Connected adapter: {adapter_id} ({adapter_type})")
                    
                    # 发现设备
                    devices = await adapter.discover_devices()
                    logger.info(f"Discovered {len(devices)} devices from adapter {adapter_id}")
                    
                else:
                    logger.error(f"Failed to connect adapter: {adapter_id}")
                
            except Exception as e:
                logger.error(f"Error loading adapter {adapter_config.get('id', 'unknown')}: {str(e)}", exc_info=True)
    
    def _on_device_status_update(self, device_id: str, status: Dict[str, Any]):
        """
        处理来自适配器的设备状态更新
        
        Args:
            device_id: 设备ID
            status: 设备状态
        """
        # 查找对应的智能设备
        device = self.get_device_by_id(device_id)
        if not device:
            logger.warning(f"Received status update for unknown device: {device_id}")
            return
            
        # 更新设备能力状态
        for cap_name, cap_value in status.items():
            if cap_name in device.capabilities:
                device.set_capability(cap_name, cap_value)
                logger.debug(f"Updated device {device_id} capability {cap_name} to {cap_value}")
    
    async def send_command_to_physical_device(self, device_id: str, command: Dict[str, Any]) -> bool:
        """
        发送命令到物理设备
        
        Args:
            device_id: 设备ID
            command: 命令数据
            
        Returns:
            命令是否成功发送
        """
        # 查找设备对应的适配器
        device = self.get_device_by_id(device_id)
        if not device or not hasattr(device, 'adapter_id'):
            logger.error(f"Device {device_id} not found or not associated with adapter")
            return False
            
        adapter_id = device.adapter_id
        adapter = self.adapters.get(adapter_id)
        if not adapter:
            logger.error(f"Adapter {adapter_id} not found")
            return False
            
        # 发送命令
        return await adapter.send_command(device_id, command)
    
    async def associate_physical_devices(self, physical_devices_config: List[Dict[str, Any]]):
        """
        将物理设备与虚拟设备模型关联
        
        Args:
            physical_devices_config: 物理设备配置列表
        """
        for device_config in physical_devices_config:
            try:
                # 获取必要的信息
                device_id = device_config.get("id")
                adapter_id = device_config.get("adapter_id")
                physical_id = device_config.get("device_id")
                
                if not all([device_id, adapter_id, physical_id]):
                    logger.error(f"Missing required physical device configuration: {device_config}")
                    continue
                    
                # 获取虚拟设备和适配器
                virtual_device = self.get_device_by_id(device_id)
                adapter = self.adapters.get(adapter_id)
                
                if not virtual_device:
                    logger.error(f"Virtual device not found: {device_id}")
                    continue
                    
                if not adapter:
                    logger.error(f"Adapter not found: {adapter_id}")
                    continue
                    
                # 为虚拟设备添加适配器信息
                virtual_device.adapter_id = adapter_id
                virtual_device.physical_device_id = physical_id
                
                logger.info(f"Associated device {device_id} with physical device {physical_id} via adapter {adapter_id}")
                
            except Exception as e:
                logger.error(f"Error associating physical device: {str(e)}")
