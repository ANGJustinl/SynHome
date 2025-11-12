#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Smart Memory Demo

演示智能记忆系统的基本功能
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def demo_smart_memory():
    """演示智能记忆系统"""
    print("🏠 SynHome 智能记忆系统演示")
    print("=" * 50)

    # 获取API密钥
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 ZHIPUAI_API_KEY")
        return

    try:
        # 导入必要模块
        from libs.devices.smart_device_manager import SmartDeviceManager
        from libs.memory.memory_manager import SmartMemoryManager

        # 1. 初始化智能设备管理器
        print("\n📱 初始化智能设备管理器...")
        smart_manager = SmartDeviceManager(user_id="demo_user", enable_memory=True)

        # 2. 模拟设备配置
        devices_config = [
            {
                "id": "thermostat_001",
                "name": "客厅空调",
                "type": "thermostat",
                "capabilities": {
                    "temperature": {
                        "type": "number",
                        "min": 16.0,
                        "max": 32.0,
                        "unit": "°C",
                        "current_value": 24.0
                    },
                    "power": {
                        "type": "switch",
                        "states": ["on", "off"],
                        "current_value": "off"
                    }
                },
                "current_state": {
                    "temperature": 24.0,
                    "power": "off",
                    "device_name": "客厅空调"
                }
            },
            {
                "id": "light_001",
                "name": "客厅主灯",
                "type": "light",
                "capabilities": {
                    "brightness": {
                        "type": "number",
                        "min": 0.0,
                        "max": 100.0,
                        "unit": "%",
                        "current_value": 80.0
                    },
                    "power": {
                        "type": "switch",
                        "states": ["on", "off"],
                        "current_value": "on"
                    }
                },
                "current_state": {
                    "brightness": 80.0,
                    "power": "on",
                    "device_name": "客厅主灯"
                }
            }
        ]

        # 3. 加载设备并启用智能控制
        print("🔧 加载设备配置...")
        smart_manager.load_devices_from_config(devices_config)
        smart_manager.enable_smart_control(api_key)

        # 4. 模拟用户交互序列
        print("\n💬 模拟用户交互序列...")

        interactions = [
            {
                "command": "打开空调",
                "time": "07:00",
                "context": {"temperature": 22, "user_activity": "morning_routine"}
            },
            {
                "command": "设置空调到26度",
                "time": "07:05",
                "context": {"temperature": 22, "user_activity": "morning_routine"}
            },
            {
                "command": "调暗灯光到50%",
                "time": "07:10",
                "context": {"temperature": 22, "user_activity": "morning_routine"}
            },
            {
                "command": "关闭空调",
                "time": "09:00",
                "context": {"temperature": 24, "user_activity": "leaving_home"}
            },
            {
                "command": "打开空调",
                "time": "18:00",
                "context": {"temperature": 28, "user_activity": "returning_home"}
            },
            {
                "command": "设置空调到23度",
                "time": "18:05",
                "context": {"temperature": 28, "user_activity": "relaxing"}
            }
        ]

        # 5. 执行交互并展示记忆效果
        for i, interaction in enumerate(interactions, 1):
            print(f"\n⏰ 交互 {i}: {interaction['time']}")
            print(f"📝 命令: {interaction['command']}")

            result = await smart_manager.process_smart_command(
                command=interaction['command'],
                device_hint="thermostat" if "空调" in interaction['command'] else "light",
                environmental_context=interaction['context']
            )

            if result['success']:
                print(f"✅ 执行成功: {result['device_name']}")
                if result.get('memory_insights', {}).get('enhanced_by_memory'):
                    print(f"🧠 记忆增强: 是")
                    suggestions = result.get('memory_insights', {}).get('habit_suggestions', [])
                    if suggestions:
                        print(f"💡 个性化建议: {suggestions[0].get('message', 'No suggestion')}")
                else:
                    print(f"🧠 记忆增强: 否 (首次交互)")
            else:
                print(f"❌ 执行失败: {result.get('error', 'Unknown error')}")

            # 模拟时间间隔
            await asyncio.sleep(1)

        # 6. 展示学习结果
        print("\n📊 用户习惯分析结果...")

        # 获取记忆摘要
        memory_summary = smart_manager.get_memory_summary()
        if 'error' not in memory_summary:
            print(f"📈 总交互次数: {memory_summary['statistics']['total_interactions']}")
            print(f"🎯 学习的模式数: {memory_summary['statistics']['learned_patterns']}")

        # 获取用户习惯
        user_habits = smart_manager.get_user_habits()
        if 'error' not in user_habits and user_habits.get('profile'):
            profile = user_habits['profile']
            print(f"\n🎭 用户习惯画像:")

            if profile.get('usage_preferences'):
                prefs = profile['usage_preferences']
                if prefs.get('most_used_devices'):
                    print(f"  • 最常用设备: {', '.join(prefs['most_used_devices'])}")
                if prefs.get('peak_hours'):
                    print(f"  • 活跃时段: {', '.join(f'{h}:00' for h in prefs['peak_hours'])}")
                if prefs.get('favorite_actions'):
                    print(f"  • 常用操作: {', '.join(prefs['favorite_actions'])}")

        # 7. 测试个性化建议
        print("\n🤖 测试个性化建议...")

        # 模拟早上7点的命令
        morning_result = await smart_manager.process_smart_command(
            command="打开空调",
            device_hint="thermostat",
            environmental_context={
                "temperature": 23,
                "user_activity": "morning_routine"
            }
        )

        if morning_result.get('memory_insights', {}).get('habit_suggestions'):
            print("✅ 检测到个性化建议:")
            for suggestion in morning_result['memory_insights']['habit_suggestions']:
                print(f"  💡 {suggestion.get('message')} (置信度: {suggestion.get('confidence', 0):.2f})")
        else:
            print("ℹ️  暂无个性化建议 (需要更多交互学习)")

        # 8. 演示记忆导出
        print("\n💾 演示记忆导出...")
        export_success = smart_manager.export_user_memories("demo_memory_export.json")
        if export_success:
            print("✅ 记忆数据已导出到 demo_memory_export.json")
        else:
            print("❌ 记忆导出失败")

        print("\n🎉 演示完成！")
        print("💡 智能记忆系统已成功:")
        print("  • 记录用户交互历史")
        print("  • 学习使用时间模式")
        print("  • 识别设备使用偏好")
        print("  • 提供个性化建议")
        print("  • 支持记忆数据导出")

    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        print("请确保所有必要的模块都已正确安装")
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        logger.exception("Demo error")


if __name__ == "__main__":
    asyncio.run(demo_smart_memory())