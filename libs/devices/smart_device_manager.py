#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Smart Device Manager with Memory Integration

集成智能记忆系统的设备管理器，提供个性化设备控制
"""

import logging
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from .device_manager import DeviceManager
from .smart_device import SmartDevice
from ..memory import SmartMemoryManager

logger = logging.getLogger(__name__)


class SmartDeviceManager(DeviceManager):
    """
    智能设备管理器

    扩展原有DeviceManager，集成记忆学习和个性化功能
    """

    def __init__(self, user_id: str = "default", enable_memory: bool = True):
        """
        初始化智能设备管理器

        Args:
            user_id: 用户ID，用于个性化记忆
            enable_memory: 是否启用记忆功能
        """
        super().__init__()

        self.user_id = user_id
        self.enable_memory = enable_memory
        self.memory_managers: Dict[str, SmartMemoryManager] = {}

        # 记忆配置
        self.memory_config = {
            "max_token_limit": 2000,
            "memory_window_hours": 24,
            "learning_window_days": 30,
            "min_pattern_occurrences": 3,
            "model": "glm-4-plus"
        }

    def enable_smart_control(self, api_key: str):
        """
        启用智能控制（包含记忆功能）

        Args:
            api_key: ZhipuAI API密钥
        """
        # 启用原有的LLM控制
        super().enable_llm_control(api_key)

        # 启用智能记忆功能
        if self.enable_memory:
            self._initialize_memory_managers(api_key)

    def _initialize_memory_managers(self, api_key: str):
        """初始化记忆管理器"""
        try:
            # 创建用户主记忆管理器
            self.memory_managers["user"] = SmartMemoryManager(
                user_id=self.user_id,
                zhipuai_api_key=api_key,
                config=self.memory_config
            )

            logger.info(f"Smart memory enabled for user {self.user_id}")

        except Exception as e:
            logger.error(f"Error initializing memory managers: {str(e)}")
            self.enable_memory = False

    async def process_smart_command(
        self,
        command: str,
        device_hint: str = None,
        environmental_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理智能命令（包含记忆和个性化）

        Args:
            command: 自然语言命令
            device_hint: 设备提示
            environmental_context: 环境上下文（温度、时间等）
            user_context: 用户上下文（位置、活动等）

        Returns:
            包含执行结果、建议和记忆信息的响应
        """
        try:
            # 获取设备信息
            device = self._get_device_for_command(command, device_hint)
            if not device:
                return {
                    "success": False,
                    "error": f"No device found for command: {command}",
                    "suggestions": self._suggest_device_for_command(command)
                }

            device_type = device.type
            current_state = device.get_current_state()

            # 如果启用记忆，使用智能处理
            if self.enable_memory and self.memory_managers.get("user"):
                memory_result = await self._process_with_memory(
                    command=command,
                    device=device,
                    device_type=device_type,
                    current_state=current_state,
                    environmental_context=environmental_context,
                    user_context=user_context
                )
            else:
                # 回退到基本处理
                memory_result = await self._process_basic(
                    command=command,
                    device=device,
                    device_type=device_type,
                    current_state=current_state
                )

            return memory_result

        except Exception as e:
            logger.error(f"Error processing smart command: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "command": command
            }

    async def _process_with_memory(
        self,
        command: str,
        device: SmartDevice,
        device_type: str,
        current_state: Dict[str, Any],
        environmental_context: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """使用记忆系统处理命令"""
        try:
            memory_manager = self.memory_managers["user"]

            # 合并环境上下文
            full_context = {
                **(environmental_context or {}),
                **(user_context or {}),
                "device_id": device.id,
                "device_name": device.name
            }

            # 使用记忆管理器处理
            result = await memory_manager.process_user_command(
                command=command,
                device_type=device_type,
                current_state=current_state,
                environmental_context=full_context
            )

            # 执行解析后的命令
            parsed_command = result["parsed_command"]
            if parsed_command.get("command"):
                execution_result = await self._execute_parsed_command(
                    device=device,
                    parsed_command=parsed_command
                )
            else:
                execution_result = await device.process_command(command)

            # 组装完整响应
            response = {
                "success": execution_result.get("success", True),
                "device_id": device.id,
                "device_name": device.name,
                "device_type": device_type,
                "executed_command": parsed_command.get("command", command),
                "execution_result": execution_result,
                "memory_insights": {
                    "recent_interactions": result["memory_context"].get("recent_activity", []),
                    "detected_patterns": result["memory_context"].get("patterns", []),
                    "habit_suggestions": result["habit_suggestions"],
                    "enhanced_by_memory": result.get("enhanced_by_memory", False)
                },
                "user_profile": result.get("user_profile", {}),
                "timestamp": datetime.now().isoformat()
            }

            # 记录成功执行
            if response["success"]:
                await self._record_successful_execution(
                    device=device,
                    command=command,
                    result=response
                )

            return response

        except Exception as e:
            logger.error(f"Error processing with memory: {str(e)}")
            return await self._process_basic(command, device, device_type, current_state)

    async def _process_basic(
        self,
        command: str,
        device: SmartDevice,
        device_type: str,
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基本处理（不使用记忆）"""
        try:
            # 使用原有的命令处理
            result = await device.process_command(command)

            return {
                "success": result.get("success", True),
                "device_id": device.id,
                "device_name": device.name,
                "device_type": device_type,
                "executed_command": command,
                "execution_result": result,
                "memory_insights": {
                    "recent_interactions": [],
                    "detected_patterns": [],
                    "habit_suggestions": [],
                    "enhanced_by_memory": False
                },
                "user_profile": {},
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in basic processing: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "device_id": device.id,
                "device_name": device.name,
                "device_type": device_type,
                "executed_command": command
            }

    def _get_device_for_command(
        self,
        command: str,
        device_hint: str = None
    ) -> Optional[SmartDevice]:
        """获取命令对应的设备"""
        if device_hint:
            # 使用设备提示
            device = self.get_device_by_type(device_hint)
            if device:
                return device

        # 尝试从命令中解析设备类型
        device_keywords = {
            "空调": ["thermostat", "air_conditioner"],
            "灯": ["light"],
            "电视": ["tv"],
            "窗帘": ["curtain"],
            "空调器": ["thermostat"]
        }

        for keyword, device_types in device_keywords.items():
            if keyword in command:
                for device_type in device_types:
                    device = self.get_device_by_type(device_type)
                    if device:
                        return device

        # 英文关键词
        english_keywords = {
            "thermostat": ["thermostat", "air", "conditioning", "temperature"],
            "light": ["light", "brightness", "lamp"],
            "tv": ["tv", "television"],
            "curtain": ["curtain", "blind"]
        }

        command_lower = command.lower()
        for device_type, keywords in english_keywords.items():
            if any(keyword in command_lower for keyword in keywords):
                device = self.get_device_by_type(device_type)
                if device:
                    return device

        # 如果没有找到，返回第一个可用设备
        if self.devices:
            logger.info(f"No device found for command '{command}', using first available device")
            return list(self.devices.values())[0]

        return None

    def _suggest_device_for_command(self, command: str) -> List[str]:
        """为命令建议设备"""
        suggestions = []
        available_types = [device.type for device in self.devices.values()]

        # 基于关键词的建议
        if any(word in command.lower() for word in ["温度", "热", "冷", "空调"]):
            suggestions.extend([t for t in available_types if "thermostat" in t or "air" in t])

        if any(word in command.lower() for word in ["灯", "光", "亮"]):
            suggestions.extend([t for t in available_types if "light" in t])

        if any(word in command.lower() for word in ["电视", "看"]):
            suggestions.extend([t for t in available_types if "tv" in t])

        return list(set(suggestions))  # 去重

    async def _execute_parsed_command(
        self,
        device: SmartDevice,
        parsed_command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行解析后的命令"""
        try:
            command = parsed_command.get("command", "")
            parameters = parsed_command.get("parameters", {})

            # 构建完整命令
            if parameters:
                full_command = f"{command} {parameters}"
            else:
                full_command = command

            return await device.process_command(full_command)

        except Exception as e:
            logger.error(f"Error executing parsed command: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _record_successful_execution(
        self,
        device: SmartDevice,
        command: str,
        result: Dict[str, Any]
    ) -> None:
        """记录成功执行"""
        try:
            # 这里可以添加额外的执行记录逻辑
            # 例如，更新设备状态、记录到日志等
            logger.info(
                f"Smart command executed successfully: {command} on {device.name}"
            )
        except Exception as e:
            logger.error(f"Error recording execution: {str(e)}")

    def get_memory_summary(self) -> Dict[str, Any]:
        """获取记忆摘要"""
        if not self.enable_memory or not self.memory_managers.get("user"):
            return {"error": "Memory not enabled"}

        return self.memory_managers["user"].get_memory_summary()

    def get_user_habits(self) -> Dict[str, Any]:
        """获取用户习惯分析"""
        if not self.enable_memory or not self.memory_managers.get("user"):
            return {"error": "Memory not enabled"}

        return {
            "profile": self.memory_managers["user"].habit_learner.get_user_profile(),
            "suggestions": []  # 可以在这里添加实时建议逻辑
        }

    def learn_manual_interaction(
        self,
        device_id: str,
        action: str,
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        学习手动交互（用于学习用户通过其他方式进行的操作）

        Args:
            device_id: 设备ID
            action: 执行的动作
            result: 执行结果
            context: 上下文信息

        Returns:
            是否成功学习
        """
        if not self.enable_memory or not self.memory_managers.get("user"):
            return False

        try:
            device = self.get_device_by_id(device_id)
            if not device:
                logger.warning(f"Device {device_id} not found for learning")
                return False

            interaction = {
                "timestamp": datetime.now().isoformat(),
                "command": action,
                "device_type": device.type,
                "action": action,
                "result": result,
                "context": context or {},
                "source": "manual_interaction"
            }

            self.memory_managers["user"].habit_learner.learn_from_interaction(interaction)
            return True

        except Exception as e:
            logger.error(f"Error learning manual interaction: {str(e)}")
            return False

    def export_user_memories(self, file_path: str) -> bool:
        """导出用户记忆"""
        if not self.enable_memory or not self.memory_managers.get("user"):
            return False

        return self.memory_managers["user"].export_memories(file_path)

    def clear_user_memories(self, days: int = 30) -> None:
        """清理用户记忆"""
        if self.enable_memory and self.memory_managers.get("user"):
            self.memory_managers["user"].clear_old_memories(days)