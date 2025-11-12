#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Smart Memory Manager

智能记忆系统管理器，整合对话记忆、习惯学习和上下文管理
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import json

from .conversation_memory import SynHomeConversationMemory
from .habit_learner import HabitLearner, HabitPattern
from .zhipuai_adapter import ZhipuAIChatAdapter

logger = logging.getLogger(__name__)


class SmartMemoryManager:
    """
    智能记忆管理器

    统一管理用户对话记忆、习惯学习和上下文感知
    """

    def __init__(
        self,
        user_id: str,
        zhipuai_api_key: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化智能记忆管理器

        Args:
            user_id: 用户ID
            zhipuai_api_key: ZhipuAI API密钥
            config: 配置参数
        """
        self.user_id = user_id
        self.config = config or {}

        # 初始化核心组件
        self.conversation_memory = SynHomeConversationMemory(
            user_id=user_id,
            max_token_limit=self.config.get("max_token_limit", 2000),
            memory_window_hours=self.config.get("memory_window_hours", 24),
            enable_summary=self.config.get("enable_summary", True)
        )

        self.habit_learner = HabitLearner(
            learning_window_days=self.config.get("learning_window_days", 30),
            min_pattern_occurrences=self.config.get("min_pattern_occurrences", 3)
        )

        self.zhipuai_adapter = ZhipuAIChatAdapter(
            api_key=zhipuai_api_key,
            model=self.config.get("model", "glm-4-plus")
        )

        # 统计信息
        self.stats = {
            "total_interactions": 0,
            "learned_patterns": 0,
            "memory_size": 0,
            "last_activity": None
        }

        logger.info(f"SmartMemoryManager initialized for user {user_id}")

    async def process_user_command(
        self,
        command: str,
        device_type: str,
        current_state: Dict[str, Any],
        environmental_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理用户命令，包含记忆和习惯学习

        Args:
            command: 用户命令
            device_type: 设备类型
            current_state: 设备当前状态
            environmental_context: 环境上下文（温度、时间等）

        Returns:
            处理结果，包含解析的命令和建议
        """
        try:
            # 获取记忆上下文
            memory_context = await self._get_memory_context(device_type, environmental_context)

            # 保存用户消息到记忆
            self.conversation_memory.add_message(
                message=command,
                role="user",
                device_context={
                    "device_type": device_type,
                    "action": command,  # 临时，将在解析后更新
                    "context": environmental_context or {}
                }
            )

            # 使用增强的上下文分析命令
            analysis_result = self.zhipuai_adapter.analyze_device_command(
                device_type=device_type,
                current_state=current_state,
                command=command,
                memory_context=memory_context
            )

            if not analysis_result:
                # fallback to basic analysis
                analysis_result = {"command": command, "parameters": {}}

            # 获取习惯建议
            habit_suggestions = await self._get_habit_suggestions(
                device_type, environmental_context
            )

            # 学习这个交互
            await self._learn_interaction(
                command=command,
                device_type=device_type,
                result=analysis_result,
                context=environmental_context
            )

            # 更新统计
            self._update_stats()

            # 组装响应
            result = {
                "parsed_command": analysis_result,
                "memory_context": {
                    "recent_activity": memory_context.get("recent_interactions", [])[-3:],  # 最近3个
                    "patterns": memory_context.get("patterns", [])[:5]  # 前5个模式
                },
                "habit_suggestions": habit_suggestions,
                "user_profile": self.habit_learner.get_user_profile(),
                "enhanced_by_memory": bool(memory_context.get("recent_interactions"))
            }

            return result

        except Exception as e:
            logger.error(f"Error processing user command: {str(e)}")
            return {
                "parsed_command": {"command": command, "parameters": {}},
                "error": str(e),
                "memory_context": {},
                "habit_suggestions": []
            }

    async def _get_memory_context(
        self,
        device_type: str,
        environmental_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """获取记忆上下文"""
        try:
            # 获取最近的上下文
            recent_context = self.conversation_memory.get_recent_context(hours=2, max_interactions=10)

            # 获取与当前设备相关的记忆
            device_specific_context = self._get_device_specific_memory(device_type)

            # 组合上下文
            context = {
                "recent_interactions": recent_context.get("recent_interactions", []),
                "patterns": recent_context.get("patterns", []),
                "device_specific": device_specific_context,
                "environmental": environmental_context or {}
            }

            return context

        except Exception as e:
            logger.error(f"Error getting memory context: {str(e)}")
            return {}

    def _get_device_specific_memory(self, device_type: str) -> Dict[str, Any]:
        """获取设备特定记忆"""
        device_interactions = [
            interaction for interaction in self.conversation_memory.device_interactions
            if interaction.get("device_type") == device_type
        ]

        if not device_interactions:
            return {}

        # 提取设备特定的模式
        recent_interactions = device_interactions[-5:]  # 最近5次交互
        common_actions = {}
        for interaction in device_interactions:
            action = interaction.get("action")
            if action:
                common_actions[action] = common_actions.get(action, 0) + 1

        return {
            "recent_interactions": recent_interactions,
            "common_actions": sorted(common_actions.items(), key=lambda x: x[1], reverse=True),
            "total_interactions": len(device_interactions),
            "last_interaction": device_interactions[-1]["timestamp"] if device_interactions else None
        }

    async def _get_habit_suggestions(
        self,
        device_type: str,
        environmental_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """获取习惯建议"""
        try:
            current_context = {
                "device_type": device_type,
                "timestamp": datetime.now().isoformat(),
                **(environmental_context or {})
            }

            suggestions = self.habit_learner.get_habit_suggestions(current_context)

            # 过滤和增强建议
            enhanced_suggestions = []
            for suggestion in suggestions:
                # 检查建议是否相关
                if self._is_suggestion_relevant(suggestion, current_context):
                    enhanced_suggestion = {
                        **suggestion,
                        "relevance_score": self._calculate_relevance(suggestion, current_context),
                        "generated_at": datetime.now().isoformat()
                    }
                    enhanced_suggestions.append(enhanced_suggestion)

            # 按相关性排序
            enhanced_suggestions.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

            return enhanced_suggestions[:3]  # 返回前3个最相关的建议

        except Exception as e:
            logger.error(f"Error getting habit suggestions: {str(e)}")
            return []

    def _is_suggestion_relevant(
        self,
        suggestion: Dict[str, Any],
        current_context: Dict[str, Any]
    ) -> bool:
        """判断建议是否相关"""
        try:
            # 时间相关性
            if suggestion.get("type") == "time_based":
                current_hour = datetime.now().hour
                suggestion_hour = suggestion.get("pattern", {}).get("hour")
                if suggestion_hour is not None:
                    time_diff = abs(current_hour - suggestion_hour)
                    return time_diff <= 2  # 2小时内相关

            # 设备相关性
            if suggestion.get("type") == "device_based":
                current_device = current_context.get("device_type")
                suggestion_device = suggestion.get("pattern", {}).get("device_type")
                return current_device == suggestion_device

            # 环境相关性
            if suggestion.get("type") == "environmental":
                current_temp = current_context.get("temperature")
                if current_temp:
                    temp_range = self._get_temperature_range(current_temp)
                    suggestion_temp_range = suggestion.get("pattern", {}).get("temperature_range")
                    return temp_range == suggestion_temp_range

            return True  # 默认相关

        except Exception as e:
            logger.error(f"Error checking suggestion relevance: {str(e)}")
            return False

    def _calculate_relevance(
        self,
        suggestion: Dict[str, Any],
        current_context: Dict[str, Any]
    ) -> float:
        """计算建议相关性得分"""
        base_score = suggestion.get("confidence", 0)

        try:
            # 时间调整
            if suggestion.get("type") == "time_based":
                current_hour = datetime.now().hour
                suggestion_hour = suggestion.get("pattern", {}).get("hour")
                if suggestion_hour is not None:
                    time_diff = abs(current_hour - suggestion_hour)
                    time_factor = max(0, 1 - time_diff / 12)  # 12小时外降为0
                    base_score *= time_factor

            return min(1.0, base_score)

        except Exception as e:
            logger.error(f"Error calculating relevance: {str(e)}")
            return base_score

    async def _learn_interaction(
        self,
        command: str,
        device_type: str,
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> None:
        """学习交互"""
        try:
            # 构建交互数据
            interaction = {
                "timestamp": datetime.now().isoformat(),
                "command": command,
                "device_type": device_type,
                "action": result.get("command", command),
                "result": result.get("result", {}),
                "context": context or {},
                "success": result.get("success", True)
            }

            # 添加到对话记忆
            self.conversation_memory.add_message(
                message=result.get("parsed_command", {}).get("raw_response", "Command processed"),
                role="assistant",
                device_context=interaction
            )

            # 添加到习惯学习器
            self.habit_learner.learn_from_interaction(interaction)

        except Exception as e:
            logger.error(f"Error learning interaction: {str(e)}")

    def _update_stats(self) -> None:
        """更新统计信息"""
        self.stats["total_interactions"] = len(self.conversation_memory.device_interactions)
        self.stats["learned_patterns"] = len(self.habit_learner.learned_patterns)
        self.stats["memory_size"] = len(self.conversation_memory.chat_history.messages)
        self.stats["last_activity"] = datetime.now()

    def _get_temperature_range(self, temperature: float) -> str:
        """获取温度范围"""
        if temperature < 10:
            return "cold"
        elif temperature < 20:
            return "cool"
        elif temperature < 28:
            return "comfortable"
        else:
            return "hot"

    def get_memory_summary(self) -> Dict[str, Any]:
        """获取记忆摘要"""
        try:
            return {
                "user_id": self.user_id,
                "conversation_summary": self.conversation_memory.get_memory_summary(),
                "habit_profile": self.habit_learner.get_user_profile(),
                "statistics": self.stats,
                "active_patterns": [
                    {
                        "id": pattern.pattern_id,
                        "type": pattern.pattern_type,
                        "confidence": pattern.confidence,
                        "frequency": pattern.frequency,
                        "context": pattern.context
                    }
                    for pattern in self.habit_learner.learned_patterns.values()
                    if pattern.is_active
                ]
            }

        except Exception as e:
            logger.error(f"Error generating memory summary: {str(e)}")
            return {"error": str(e)}

    def clear_old_memories(self, days: int = 30) -> None:
        """清理旧记忆"""
        try:
            # 清理对话记忆
            cutoff_time = datetime.now() - timedelta(days=days)
            self.conversation_memory.device_interactions = [
                interaction for interaction in self.conversation_memory.device_interactions
                if datetime.fromisoformat(interaction["timestamp"]) > cutoff_time
            ]

            # 习惯学习器会自动清理
            self.habit_learner._cleanup_old_history()

            logger.info(f"Cleared memories older than {days} days for user {self.user_id}")

        except Exception as e:
            logger.error(f"Error clearing old memories: {str(e)}")

    def export_memories(self, file_path: str) -> bool:
        """导出记忆数据"""
        try:
            export_data = {
                "user_id": self.user_id,
                "export_timestamp": datetime.now().isoformat(),
                "conversation_history": self.conversation_memory.device_interactions,
                "learned_patterns": {
                    pattern_id: {
                        "type": pattern.pattern_type,
                        "confidence": pattern.confidence,
                        "frequency": pattern.frequency,
                        "context": pattern.context,
                        "last_updated": pattern.last_updated.isoformat()
                    }
                    for pattern_id, pattern in self.habit_learner.learned_patterns.items()
                },
                "statistics": self.stats
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Memories exported to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting memories: {str(e)}")
            return False