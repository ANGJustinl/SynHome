#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SynHome Conversation Memory

基于LangChain的对话记忆系统，专为智能家居优化
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import BaseMessage
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class SynHomeConversationMemory:
    """
    SynHome专用的对话记忆系统

    特点：
    1. 按用户和会话分离记忆
    2. 保留设备交互历史
    3. 支持习惯模式提取
    4. 智能记忆压缩
    """

    def __init__(
        self,
        user_id: str,
        max_token_limit: int = 2000,
        memory_window_hours: int = 24,
        enable_summary: bool = True
    ):
        """
        初始化对话记忆

        Args:
            user_id: 用户ID
            max_token_limit: 最大token限制
            memory_window_hours: 记忆时间窗口（小时）
            enable_summary: 是否启用摘要功能
        """
        self.user_id = user_id
        self.max_token_limit = max_token_limit
        self.memory_window_hours = memory_window_hours
        self.enable_summary = enable_summary

        # LangChain记忆组件
        self.chat_history = ChatMessageHistory()

        # 标志位，标识是否启用摘要功能
        self.enable_summary = enable_summary

        # 智能家居专用数据
        self.device_interactions: List[Dict[str, Any]] = []
        self.context_store: Dict[str, Any] = {}
        self.hint_store: Dict[str, str] = {}

    def add_message(
        self,
        message: str,
        role: str,
        device_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加消息到记忆

        Args:
            message: 消息内容
            role: 用户角色 (user/assistant)
            device_context: 设备上下文信息
        """
        try:
            # 添加到LangChain记忆
            if role == "user":
                from langchain_core.messages import HumanMessage
                self.chat_history.add_message(HumanMessage(content=message))
            elif role == "assistant":
                from langchain_core.messages import AIMessage
                self.chat_history.add_message(AIMessage(content=message))

            # 记录设备交互
            if device_context:
                interaction = {
                    "timestamp": datetime.now(),
                    "message": message,
                    "role": role,
                    "device_type": device_context.get("device_type"),
                    "device_id": device_context.get("device_id"),
                    "action": device_context.get("action"),
                    "result": device_context.get("result"),
                    "context": device_context.get("context", {})
                }
                self.device_interactions.append(interaction)

                # 清理过期记忆
                self._cleanup_old_interactions()

        except Exception as e:
            logger.error(f"Error adding message to memory: {str(e)}")

    def get_recent_context(
        self,
        hours: int = 2,
        max_interactions: int = 10
    ) -> Dict[str, Any]:
        """
        获取最近的上下文信息

        Args:
            hours: 时间窗口（小时）
            max_interactions: 最大交互数

        Returns:
            包含最近交互和上下文的字典
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # 获取最近的设备交互
            recent_interactions = [
                interaction for interaction in self.device_interactions
                if interaction["timestamp"] > cutoff_time
            ]

            # 限制数量并按时间排序
            recent_interactions = sorted(
                recent_interactions,
                key=lambda x: x["timestamp"],
                reverse=True
            )[:max_interactions]

            # 提取模式信息
            patterns = self._extract_usage_patterns(recent_interactions)

            return {
                "recent_interactions": recent_interactions,
                "patterns": patterns,
                "current_session": {
                    "device_usage": self._get_device_usage(recent_interactions),
                    "time_patterns": self._get_time_patterns(recent_interactions),
                    "frequent_commands": self._get_frequent_commands(recent_interactions)
                }
            }

        except Exception as e:
            logger.error(f"Error getting recent context: {str(e)}")
            return {}

    def _cleanup_old_interactions(self) -> None:
        """清理过期的交互记录"""
        cutoff_time = datetime.now() - timedelta(hours=self.memory_window_hours)
        self.device_interactions = [
            interaction for interaction in self.device_interactions
            if interaction["timestamp"] > cutoff_time
        ]

    def _extract_usage_patterns(
        self,
        interactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        提取使用模式

        Args:
            interactions: 交互列表

        Returns:
            模式列表
        """
        patterns = []

        try:
            # 时间模式检测
            time_patterns = self._detect_time_patterns(interactions)
            patterns.extend(time_patterns)

            # 设备组合模式
            device_patterns = self._detect_device_patterns(interactions)
            patterns.extend(device_patterns)

            # 命令模式
            command_patterns = self._detect_command_patterns(interactions)
            patterns.extend(command_patterns)

        except Exception as e:
            logger.error(f"Error extracting usage patterns: {str(e)}")

        return patterns

    def _detect_time_patterns(
        self,
        interactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """检测时间模式"""
        patterns = []
        time_counts = {}

        for interaction in interactions:
            hour = interaction["timestamp"].hour
            time_counts[hour] = time_counts.get(hour, 0) + 1

        # 查找高频时段
        for hour, count in time_counts.items():
            if count >= 3:  # 至少3次交互才算模式
                patterns.append({
                    "type": "time_pattern",
                    "hour": hour,
                    "frequency": count,
                    "description": f"用户在{hour}:00-{hour+1}:00时段活跃"
                })

        return patterns

    def _detect_device_patterns(
        self,
        interactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """检测设备模式"""
        patterns = []
        device_usage = {}

        for interaction in interactions:
            device_type = interaction.get("device_type")
            if device_type:
                device_usage[device_type] = device_usage.get(device_type, 0) + 1

        # 常用设备
        for device, count in device_usage.items():
            if count >= 5:
                patterns.append({
                    "type": "device_preference",
                    "device_type": device,
                    "usage_count": count,
                    "description": f"经常使用{device}设备"
                })

        return patterns

    def _detect_command_patterns(
        self,
        interactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """检测命令模式"""
        patterns = []
        commands = {}

        for interaction in interactions:
            action = interaction.get("action")
            if action:
                commands[action] = commands.get(action, 0) + 1

        # 常用命令
        for command, count in commands.items():
            if count >= 3:
                patterns.append({
                    "type": "command_preference",
                    "command": command,
                    "usage_count": count,
                    "description": f"经常执行{command}命令"
                })

        return patterns

    def _get_device_usage(
        self,
        interactions: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """获取设备使用统计"""
        usage = {}
        for interaction in interactions:
            device = interaction.get("device_type")
            if device:
                usage[device] = usage.get(device, 0) + 1
        return usage

    def _get_time_patterns(
        self,
        interactions: List[Dict[str, Any]]
    ) -> List[int]:
        """获取时间模式"""
        hours = []
        for interaction in interactions:
            hours.append(interaction["timestamp"].hour)
        return hours

    def _get_frequent_commands(
        self,
        interactions: List[Dict[str, Any]]
    ) -> List[str]:
        """获取常用命令"""
        commands = {}
        for interaction in interactions:
            action = interaction.get("action")
            if action:
                commands[action] = commands.get(action, 0) + 1

        # 返回前5个最常用的命令
        sorted_commands = sorted(commands.items(), key=lambda x: x[1], reverse=True)
        return [cmd for cmd, _ in sorted_commands[:5]]

    def get_memory_summary(self) -> str:
        """
        获取记忆摘要

        Returns:
            记忆摘要文本
        """
        try:
            total_interactions = len(self.device_interactions)
            recent_hours = self.memory_window_hours
            recent_interactions = len([
                i for i in self.device_interactions
                if i["timestamp"] > datetime.now() - timedelta(hours=recent_hours)
            ])

            summary = f"用户{self.user_id}的记忆摘要:\n"
            summary += f"- 总交互次数: {total_interactions}\n"
            summary += f"- 最近{recent_hours}小时交互: {recent_interactions}\n"

            if self.device_interactions:
                latest_interaction = self.device_interactions[-1]
                summary += f"- 最后交互时间: {latest_interaction['timestamp']}\n"
                summary += f"- 最后交互设备: {latest_interaction.get('device_type', 'Unknown')}\n"

            return summary

        except Exception as e:
            logger.error(f"Error generating memory summary: {str(e)}")
            return f"无法生成用户{self.user_id}的记忆摘要"

    def save_context(self, context: Dict[str, Any]) -> None:
        """保存上下文信息"""
        self.context_store.update(context)

    def load_context(self) -> Dict[str, Any]:
        """加载上下文信息"""
        return self.context_store.copy()