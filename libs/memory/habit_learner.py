#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Habit Learner

用户习惯学习和模式识别系统
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import logging

logger = logging.getLogger(__name__)


class HabitPattern:
    """习惯模式数据结构"""

    def __init__(
        self,
        pattern_id: str,
        pattern_type: str,
        confidence: float,
        frequency: int,
        context: Dict[str, Any]
    ):
        self.pattern_id = pattern_id
        self.pattern_type = pattern_type
        self.confidence = confidence
        self.frequency = frequency
        self.context = context
        self.last_updated = datetime.now()
        self.is_active = True


class HabitLearner:
    """
    习惯学习器

    学习用户的设备使用习惯，识别模式并提供个性化建议
    """

    def __init__(self, learning_window_days: int = 30, min_pattern_occurrences: int = 3):
        """
        初始化习惯学习器

        Args:
            learning_window_days: 学习窗口（天）
            min_pattern_occurrences: 最小模式出现次数
        """
        self.learning_window_days = learning_window_days
        self.min_pattern_occurrences = min_pattern_occurrences
        self.learned_patterns: Dict[str, HabitPattern] = {}
        self.interaction_history: List[Dict[str, Any]] = []

    def learn_from_interaction(self, interaction: Dict[str, Any]) -> None:
        """
        从单个交互中学习

        Args:
            interaction: 交互数据
        """
        try:
            # 记录交互
            self.interaction_history.append(interaction)

            # 限制历史记录大小
            self._cleanup_old_history()

            # 学习时间模式
            self._learn_time_patterns(interaction)

            # 学习设备组合模式
            self._learn_device_combination_patterns(interaction)

            # 学习命令序列模式
            self._learn_command_sequence_patterns(interaction)

            # 学习环境模式
            self._learn_environmental_patterns(interaction)

        except Exception as e:
            logger.error(f"Error learning from interaction: {str(e)}")

    def get_habit_suggestions(
        self,
        current_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        基于当前上下文提供习惯建议

        Args:
            current_context: 当前上下文

        Returns:
            建议列表
        """
        suggestions = []

        try:
            # 时间相关建议
            time_suggestions = self._get_time_based_suggestions(current_context)
            suggestions.extend(time_suggestions)

            # 设备使用建议
            device_suggestions = self._get_device_based_suggestions(current_context)
            suggestions.extend(device_suggestions)

            # 环境相关建议
            env_suggestions = self._get_environmental_suggestions(current_context)
            suggestions.extend(env_suggestions)

            # 按置信度排序
            suggestions.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        except Exception as e:
            logger.error(f"Error generating habit suggestions: {str(e)}")

        return suggestions[:5]  # 返回前5个建议

    def get_user_profile(self) -> Dict[str, Any]:
        """
        获取用户习惯画像

        Returns:
            用户习惯画像
        """
        profile = {
            "total_interactions": len(self.interaction_history),
            "learning_period_days": self.learning_window_days,
            "active_patterns": len(self.learned_patterns),
            "patterns": {}
        }

        try:
            # 按模式类型分组
            patterns_by_type = defaultdict(list)
            for pattern in self.learned_patterns.values():
                if pattern.is_active:
                    patterns_by_type[pattern.pattern_type].append(pattern)

            # 统计各类型模式
            for pattern_type, patterns in patterns_by_type.items():
                profile["patterns"][pattern_type] = {
                    "count": len(patterns),
                    "avg_confidence": sum(p.confidence for p in patterns) / len(patterns),
                    "most_frequent": max(patterns, key=lambda p: p.frequency).context
                }

            # 使用偏好
            profile["usage_preferences"] = self._analyze_usage_preferences()

        except Exception as e:
            logger.error(f"Error generating user profile: {str(e)}")

        return profile

    def _cleanup_old_history(self) -> None:
        """清理过期历史记录"""
        cutoff_date = datetime.now() - timedelta(days=self.learning_window_days)
        self.interaction_history = [
            interaction for interaction in self.interaction_history
            if datetime.fromisoformat(interaction["timestamp"]) > cutoff_date
        ]

    def _learn_time_patterns(self, interaction: Dict[str, Any]) -> None:
        """学习时间模式"""
        try:
            timestamp = datetime.fromisoformat(interaction["timestamp"])
            hour = timestamp.hour
            day_of_week = timestamp.weekday()

            # 小时模式
            pattern_id = f"hourly_{hour}"
            self._update_pattern_frequency(
                pattern_id,
                "time_hourly",
                {
                    "hour": hour,
                    "device_type": interaction.get("device_type"),
                    "action": interaction.get("action")
                }
            )

            # 工作日/周末模式
            is_weekend = day_of_week >= 5
            pattern_id = f"daily_{day_of_week}"
            self._update_pattern_frequency(
                pattern_id,
                "time_daily",
                {
                    "day_of_week": day_of_week,
                    "is_weekend": is_weekend,
                    "device_type": interaction.get("device_type"),
                    "action": interaction.get("action")
                }
            )

        except Exception as e:
            logger.error(f"Error learning time patterns: {str(e)}")

    def _learn_device_combination_patterns(self, interaction: Dict[str, Any]) -> None:
        """学习设备组合模式"""
        try:
            device_type = interaction.get("device_type")
            if not device_type:
                return

            # 设备使用频率
            pattern_id = f"device_{device_type}"
            self._update_pattern_frequency(
                pattern_id,
                "device_preference",
                {
                    "device_type": device_type,
                    "action": interaction.get("action"),
                    "time_context": self._get_time_context(interaction)
                }
            )

        except Exception as e:
            logger.error(f"Error learning device patterns: {str(e)}")

    def _learn_command_sequence_patterns(self, interaction: Dict[str, Any]) -> None:
        """学习命令序列模式"""
        try:
            if len(self.interaction_history) < 2:
                return

            # 查找前一个交互
            current_time = datetime.fromisoformat(interaction["timestamp"])
            prev_interaction = None

            for hist_interaction in reversed(self.interaction_history[:-1]):
                hist_time = datetime.fromisoformat(hist_interaction["timestamp"])
                time_diff = current_time - hist_time

                # 只考虑5分钟内的交互
                if time_diff.total_seconds() <= 300:
                    prev_interaction = hist_interaction
                    break

            if prev_interaction:
                # 创建序列模式
                prev_device = prev_interaction.get("device_type")
                curr_device = interaction.get("device_type")

                if prev_device and curr_device:
                    pattern_id = f"sequence_{prev_device}_to_{curr_device}"
                    self._update_pattern_frequency(
                        pattern_id,
                        "sequence_pattern",
                        {
                            "from_device": prev_device,
                            "to_device": curr_device,
                            "time_gap_minutes": time_diff.total_seconds() / 60
                        }
                    )

        except Exception as e:
            logger.error(f"Error learning command sequence patterns: {str(e)}")

    def _learn_environmental_patterns(self, interaction: Dict[str, Any]) -> None:
        """学习环境模式"""
        try:
            context = interaction.get("context", {})
            if not context:
                return

            # 温度相关模式
            temperature = context.get("temperature")
            device_type = interaction.get("device_type")

            if temperature and device_type:
                temp_range = self._get_temperature_range(temperature)
                pattern_id = f"temp_{temp_range}_{device_type}"
                self._update_pattern_frequency(
                    pattern_id,
                    "environmental",
                    {
                        "temperature_range": temp_range,
                        "device_type": device_type,
                        "action": interaction.get("action")
                    }
                )

        except Exception as e:
            logger.error(f"Error learning environmental patterns: {str(e)}")

    def _update_pattern_frequency(
        self,
        pattern_id: str,
        pattern_type: str,
        context: Dict[str, Any]
    ) -> None:
        """更新模式频率"""
        if pattern_id in self.learned_patterns:
            pattern = self.learned_patterns[pattern_id]
            pattern.frequency += 1
            pattern.last_updated = datetime.now()
            # 提高置信度
            pattern.confidence = min(1.0, pattern.confidence + 0.1)
        else:
            pattern = HabitPattern(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                confidence=0.1,
                frequency=1,
                context=context
            )
            self.learned_patterns[pattern_id] = pattern

        # 如果频率足够，激活模式
        if pattern.frequency >= self.min_pattern_occurrences:
            pattern.is_active = True

    def _get_time_based_suggestions(self, current_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取基于时间的建议"""
        suggestions = []
        current_hour = datetime.now().hour

        time_patterns = [
            pattern for pattern in self.learned_patterns.values()
            if (pattern.pattern_type == "time_hourly" and
                pattern.context.get("hour") == current_hour and
                pattern.is_active)
        ]

        for pattern in time_patterns:
            if pattern.confidence >= 0.5:
                suggestion = {
                    "type": "time_based",
                    "confidence": pattern.confidence,
                    "message": f"根据您的使用习惯，这个时候您经常使用{pattern.context.get('device_type')}",
                    "suggested_action": pattern.context.get("action"),
                    "pattern": pattern.context
                }
                suggestions.append(suggestion)

        return suggestions

    def _get_device_based_suggestions(self, current_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取基于设备的建议"""
        suggestions = []
        current_device = current_context.get("device_type")

        if current_device:
            device_patterns = [
                pattern for pattern in self.learned_patterns.values()
                if (pattern.pattern_type == "device_preference" and
                   pattern.context.get("device_type") == current_device and
                   pattern.is_active)
            ]

            for pattern in device_patterns:
                if pattern.confidence >= 0.6:
                    suggestion = {
                        "type": "device_based",
                        "confidence": pattern.confidence,
                        "message": f"您经常对这个设备执行{pattern.context.get('action')}操作",
                        "suggested_action": pattern.context.get("action"),
                        "pattern": pattern.context
                    }
                    suggestions.append(suggestion)

        return suggestions

    def _get_environmental_suggestions(self, current_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取环境相关建议"""
        suggestions = []
        temperature = current_context.get("temperature")

        if temperature:
            temp_range = self._get_temperature_range(temperature)
            env_patterns = [
                pattern for pattern in self.learned_patterns.values()
                if (pattern.pattern_type == "environmental" and
                   pattern.context.get("temperature_range") == temp_range and
                   pattern.is_active)
            ]

            for pattern in env_patterns:
                if pattern.confidence >= 0.4:
                    suggestion = {
                        "type": "environmental",
                        "confidence": pattern.confidence,
                        "message": f"在当前温度条件下，您通常会{pattern.context.get('action')}这个设备",
                        "suggested_action": pattern.context.get("action"),
                        "pattern": pattern.context
                    }
                    suggestions.append(suggestion)

        return suggestions

    def _get_time_context(self, interaction: Dict[str, Any]) -> str:
        """获取时间上下文"""
        timestamp = datetime.fromisoformat(interaction["timestamp"])
        hour = timestamp.hour

        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"

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

    def _analyze_usage_preferences(self) -> Dict[str, Any]:
        """分析使用偏好"""
        preferences = {
            "most_used_devices": [],
            "peak_hours": [],
            "favorite_actions": []
        }

        try:
            # 设备使用统计
            device_counter = Counter()
            hour_counter = Counter()
            action_counter = Counter()

            for interaction in self.interaction_history:
                device_type = interaction.get("device_type")
                if device_type:
                    device_counter[device_type] += 1

                timestamp = datetime.fromisoformat(interaction["timestamp"])
                hour_counter[timestamp.hour] += 1

                action = interaction.get("action")
                if action:
                    action_counter[action] += 1

            # 获取前3
            preferences["most_used_devices"] = [
                device for device, _ in device_counter.most_common(3)
            ]
            preferences["peak_hours"] = [
                hour for hour, _ in hour_counter.most_common(3)
            ]
            preferences["favorite_actions"] = [
                action for action, _ in action_counter.most_common(3)
            ]

        except Exception as e:
            logger.error(f"Error analyzing usage preferences: {str(e)}")

        return preferences