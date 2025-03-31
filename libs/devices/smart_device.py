#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Smart device base class with dynamic capability handling
"""

import logging
import re  # 添加正则表达式模块
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from .interface import DeviceState
from ..utils.llm import ZhipuAIClient

logger = logging.getLogger(__name__)

class CapabilityType(Enum):
    SWITCH = "switch"
    NUMBER = "number"
    ENUM = "enum"

@dataclass
class Capability:
    """Device capability definition"""
    name: str
    type: CapabilityType
    states: List[str] = None  # For switch type
    values: List[str] = None  # For enum type
    min_value: float = None   # For number type
    max_value: float = None   # For number type
    unit: str = None          # For number type
    current_value: Any = None

class SmartDevice:
    """Smart device with dynamic capabilities"""

    def __init__(self, device_id: str, config: Dict[str, Any]):
        self.id = device_id
        self.name = config["name"]
        self.type = config["type"]
        self.capabilities: Dict[str, Capability] = {}
        self.state = DeviceState.IDLE
        self.llm_client: Optional[ZhipuAIClient] = None
        
        # Load capabilities from config
        for cap_dict in config["capabilities"]:
            for cap_name, cap_config in cap_dict.items():
                cap_type = CapabilityType(cap_config["type"])
                
                if cap_type == CapabilityType.SWITCH:
                    self.capabilities[cap_name] = Capability(
                            name=cap_name,
                        type=cap_type,
                        states=cap_config["states"],
                        current_value="off"
                    )
                elif cap_type == CapabilityType.NUMBER:
                    self.capabilities[cap_name] = Capability(
                            name=cap_name,
                        type=cap_type,
                        min_value=cap_config["min"],
                        max_value=cap_config["max"],
                        unit=cap_config.get("unit"),
                        current_value=cap_config["min"]
                    )
                elif cap_type == CapabilityType.ENUM:
                    self.capabilities[cap_name] = Capability(
                            name=cap_name,
                        type=cap_type,
                        values=cap_config["values"],
                        current_value=cap_config["values"][0]
                    )

    def enable_llm_control(self, api_key: str):
        """Enable LLM control"""
        self.llm_client = ZhipuAIClient(api_key)

    def get_capability_info(self) -> Dict[str, Any]:
        """Get device capabilities information"""
        info = {}
        for name, cap in self.capabilities.items():
            cap_info = {
                    "type": cap.type.value,
                "current_value": cap.current_value
            }
            
            if cap.type == CapabilityType.SWITCH:
                cap_info["states"] = cap.states
            elif cap.type == CapabilityType.NUMBER:
                cap_info.update({
                        "min": cap.min_value,
                    "max": cap.max_value,
                    "unit": cap.unit
                })
            elif cap.type == CapabilityType.ENUM:
                cap_info["values"] = cap.values
                
            info[name] = cap_info
        return info

    def set_capability(self, name: str, value: Any) -> bool:
        """Set capability value"""
        if name not in self.capabilities:
            logger.error(f"Capability {name} not found")
            return False
            
        cap = self.capabilities[name]
        
        try:
            # 预处理值，去除单位后缀
            value = self._sanitize_value(name, value)
            
            if cap.type == CapabilityType.SWITCH:
                if value not in cap.states:
                    raise ValueError(f"Invalid state {value} for {name}")
                cap.current_value = value
                self.state = DeviceState.ON if value == "on" else DeviceState.OFF
                
            elif cap.type == CapabilityType.NUMBER:
                num_value = float(value)
                if not (cap.min_value <= num_value <= cap.max_value):
                    raise ValueError(f"Value {value} out of range for {name}")
                cap.current_value = num_value
                
            elif cap.type == CapabilityType.ENUM:
                if value not in cap.values:
                    raise ValueError(f"Invalid value {value} for {name}")
                cap.current_value = value
                
            return True
            
        except Exception as e:
            logger.error(f"Error setting capability {name}: {str(e)}")
            return False
    
    def _sanitize_value(self, capability_name: str, value: Any) -> Any:
        """处理参数值，去除单位后缀并转换为适当的类型"""
        if not isinstance(value, str):
            return value
            
        # 获取能力信息
        if capability_name not in self.capabilities:
            return value
            
        capability = self.capabilities[capability_name]
        
        # 处理数值类型，去除常见单位
        if capability.type == CapabilityType.NUMBER:
            # 移除单位后缀
            value = self._strip_unit_suffix(value)
            
        return value
    
    def _strip_unit_suffix(self, value_str: str) -> str:
        """移除常见的单位后缀，如%、°C等"""
        if not isinstance(value_str, str):
            return value_str
            
        # 定义常见单位模式
        unit_patterns = [
            r'%',           # 百分比
            r'°C|°F',       # 温度单位
            r'度|分钟|小时|秒',  # 其他常见单位
            r'\s+',         # 空白字符
        ]
        
        result = value_str
        for pattern in unit_patterns:
            result = re.sub(pattern, '', result)
            
        return result

    def process_natural_command(self, command: str) -> bool:
        """Process natural language command using LLM"""
        if not self.llm_client:
            logger.error("LLM control not enabled")
            return False
            
        try:
            # Get current context
            context = {
                "device_type": self.type,
                "device_name": self.name,
                "current_state": self.state.value,
                "capabilities": self.get_capability_info()
            }
            
            # Use LLM to analyze command
            result = self.llm_client.analyze_device_control(
                device_type=self.type,
                current_state=context,
                command=command
            )
            
            if not result:
                return False
                
            # 处理复合命令（多个操作）
            if "compound" in result and result.get("compound") and "operations" in result:
                logger.info(f"执行复合命令，共{len(result['operations'])}个操作")
                success = True
                
                # 优先处理电源操作
                power_operation = None
                other_operations = []
                
                # 分离电源操作和其他操作
                for operation in result["operations"]:
                    cmd = operation.get("command", "")
                    if cmd in ["on", "turn_on", "off", "turn_off"]:
                        power_operation = operation
                    else:
                        other_operations.append(operation)
                
                # 先执行电源操作
                if power_operation:
                    cmd = power_operation.get("command", "")
                    params = power_operation.get("params", {}) or {}
                    logger.info(f"优先执行电源操作: {cmd}")
                    if not self._process_single_operation(cmd, params):
                        success = False
                        logger.warning(f"电源操作失败: {cmd}")
                
                # 然后执行其他操作
                for operation in other_operations:
                    cmd = operation.get("command", "")
                    params = operation.get("params", {}) or {}
                    
                    logger.info(f"执行操作: {cmd} 参数: {params}")
                    
                    # 处理操作，如果任一操作失败，则标记整体失败但继续执行剩余操作
                    if cmd and not self._process_single_operation(cmd, params):
                        success = False
                        logger.warning(f"操作执行失败: {cmd}")
                
                return success
            
            # 处理单个操作命令
            cmd = result.get("command", "")
            params = result.get("params", {}) or {}
            
            # 处理LLM返回结果
            logger.info(f"LLM response: {result}")
            return self._process_single_operation(cmd, params)
            
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            return False

    def _process_single_operation(self, cmd: str, params: dict) -> bool:
        """处理单个操作指令"""
        # 处理常见指令模式
        if self._handle_common_command(cmd, params):
            return True
            
        # 处理设置类指令 (set_xxx)
        if cmd.startswith("set_") and self._handle_set_command(cmd, params):
            return True
            
        # 处理特殊动作指令
        if self._handle_action_command(cmd, params):
            return True
            
        logger.error(f"Unsupported command format: cmd={cmd}, params={params}")
        return False

    def _handle_common_command(self, cmd: str, params: dict) -> bool:
        """Handle common commands like on/off"""
        # 电源开关命令
        if cmd in ["on", "off", "turn_on", "turn_off"]:
            actual_cmd = "on" if cmd in ["on", "turn_on"] else "off"
            return self.set_capability("power", actual_cmd)
            
        return False
        
    def _handle_set_command(self, cmd: str, params: dict) -> bool:
        """Handle set_xxx type commands"""
        # 检查设备是否已开启，如果未开启且有power能力，先开启设备
        if "power" in self.capabilities:
            power_cap = self.capabilities["power"]
            if power_cap.current_value == "off":
                logger.info(f"设备 {self.name} 当前关闭，自动开启后再设置参数")
                self.set_capability("power", "on")
        
        # 去掉set_前缀
        capability = cmd[4:]
        
        # 如果直接匹配能力名称
        if capability in self.capabilities:
            # 如果参数中包含能力名称的参数
            if capability in params:
                return self.set_capability(capability, params[capability])
            # 如果只有一个参数，直接使用它
            elif len(params) == 1:
                return self.set_capability(capability, next(iter(params.values())))
        
        # 处理多参数情况 - 遍历所有参数尝试设置对应能力
        success = True
        for param_name, param_value in params.items():
            if param_name in self.capabilities:
                if not self.set_capability(param_name, param_value):
                    success = False
            
        return success
        
    def _handle_action_command(self, cmd: str, params: dict) -> bool:
        """Handle special action commands like start_cooking"""
        # 检查设备是否已开启（对于非关机命令）
        if cmd != "stop_cooking" and cmd != "stop" and cmd != "cancel" and cmd != "off" and cmd != "turn_off":
            if "power" in self.capabilities:
                power_cap = self.capabilities["power"]
                if power_cap.current_value == "off":
                    logger.info(f"设备 {self.name} 当前关闭，自动开启后再执行 {cmd}")
                    self.set_capability("power", "on")
        
        # 开始烹饪
        if cmd == "start_cooking" or cmd == "start":
            # 设备已在上面开启，不需要重复操作
            result = True
            
            # 如果指定了程序，设置程序
            if "program" in params and "program" in self.capabilities:
                result = self.set_capability("program", params["program"]) and result
                
            # 更新设备状态为运行中
            self.state = DeviceState.RUNNING
            return result
        
        # 停止/结束操作
        if cmd == "stop_cooking" or cmd == "stop" or cmd == "cancel":
            # 设置电源关闭
            result = self.set_capability("power", "off")
            self.state = DeviceState.OFF
            return result
            
        return False