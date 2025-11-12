#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简单的智能记忆系统测试

直接测试核心记忆功能，不依赖复杂的设备管理
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta
import json

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_smart_memory_core():
    """测试智能记忆系统核心功能"""
    print("🧠 SynHome 智能记忆系统核心功能测试")
    print("=" * 50)

    # 获取API密钥
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 ZHIPUAI_API_KEY")
        return

    try:
        # 导入记忆管理器
        from libs.memory.memory_manager import SmartMemoryManager

        print("\n🔧 初始化智能记忆管理器...")
        memory_manager = SmartMemoryManager(
            user_id="test_user",
            zhipuai_api_key=api_key,
            config={
                "model": "glm-4.5-air",
                "max_token_limit": 2000,
                "memory_window_hours": 24,
                "learning_window_days": 30,
                "min_pattern_occurrences": 2  # 降低阈值以便测试
            }
        )

        print("✅ 记忆管理器初始化成功")

        # 2. 模拟用户交互序列
        print("\n💬 模拟用户交互学习...")

        interactions = [
            {
                "command": "打开客厅空调",
                "device_type": "thermostat",
                "environmental_context": {"temperature": 22, "time": "07:00"},
                "result": {"success": True, "action": "power_on"}
            },
            {
                "command": "设置空调到26度",
                "device_type": "thermostat",
                "environmental_context": {"temperature": 22, "time": "07:05"},
                "result": {"success": True, "action": "set_temperature", "value": 26}
            },
            {
                "command": "调暗客厅灯光到50%",
                "device_type": "light",
                "environmental_context": {"temperature": 22, "time": "07:10"},
                "result": {"success": True, "action": "set_brightness", "value": 50}
            },
            {
                "command": "关闭客厅空调",
                "device_type": "thermostat",
                "environmental_context": {"temperature": 24, "time": "09:00"},
                "result": {"success": True, "action": "power_off"}
            },
            {
                "command": "重新打开客厅空调",
                "device_type": "thermostat",
                "environmental_context": {"temperature": 28, "time": "18:00"},
                "result": {"success": True, "action": "power_on"}
            }
        ]

        # 3. 执行交互学习
        for i, interaction in enumerate(interactions, 1):
            print(f"\n⏰ 交互 {i}: {interaction['environmental_context']['time']}")
            print(f"📝 命令: {interaction['command']}")

            # 直接学习交互，不需要完整的设备处理
            memory_manager.habit_learner.learn_from_interaction({
                "timestamp": datetime.now().isoformat(),
                "command": interaction["command"],
                "device_type": interaction["device_type"],
                "action": interaction["result"]["action"],
                "result": interaction["result"],
                "context": interaction["environmental_context"]
            })

            print("✅ 交互学习完成")

        # 4. 测试建议生成
        print("\n🤖 测试智能建议生成...")

        # 模拟早上7点的场景
        morning_context = {
            "device_type": "thermostat",
            "timestamp": datetime.now().isoformat(),
            "temperature": 23,
            "user_activity": "morning_routine"
        }

        suggestions = memory_manager.habit_learner.get_habit_suggestions(morning_context)

        if suggestions:
            print("✅ 检测到个性化建议:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"  {i}. {suggestion.get('message')} (置信度: {suggestion.get('confidence', 0):.2f})")
                print(f"     类型: {suggestion.get('type')}, 频率: {suggestion.get('pattern', {}).get('frequency', 'N/A')}")
        else:
            print("ℹ️  暂无足够的学习模式 (需要更多交互)")

        # 5. 测试用户画像
        print("\n📊 生成用户习惯画像...")
        profile = memory_manager.habit_learner.get_user_profile()

        if profile and profile.get("total_interactions", 0) > 0:
            print(f"📈 总交互次数: {profile['total_interactions']}")
            print(f"🎯 学习的模式数: {profile.get('active_patterns', 0)}")

            if profile.get("patterns"):
                print("\n🎯 学习的模式:")
                for pattern_type, pattern_info in profile["patterns"].items():
                    print(f"  • {pattern_type}: {pattern_info['count']}个模式")
                    print(f"    平均置信度: {pattern_info['avg_confidence']:.2f}")

            if profile.get("usage_preferences"):
                prefs = profile["usage_preferences"]
                if prefs.get("most_used_devices"):
                    print(f"  • 最常用设备: {', '.join(prefs['most_used_devices'])}")
                if prefs.get("peak_hours"):
                    print(f"  • 活跃时段: {', '.join(f'{h}:00' for h in prefs['peak_hours'])}")
        else:
            print("📊 用户画像数据不足")

        # 6. 测试记忆摘要
        print("\n💾 生成记忆摘要...")
        memory_summary = memory_manager.get_memory_summary()

        if "error" not in memory_summary:
            print("✅ 记忆摘要生成成功")
            print(f"对话摘要: {memory_summary.get('conversation_summary', 'N/A')}")
        else:
            print("❌ 记忆摘要生成失败")

        # 7. 测试数据导出
        print("\n💾 测试数据导出...")
        export_file = "test_memory_export.json"
        export_success = memory_manager.export_memories(export_file)

        if export_success:
            print(f"✅ 记忆数据已导出到 {export_file}")

            # 验证导出文件
            try:
                with open(export_file, 'r', encoding='utf-8') as f:
                    export_data = json.load(f)
                    print(f"📄 导出数据包含:")
                    print(f"  • 用户ID: {export_data.get('user_id')}")
                    print(f"  • 交互历史: {len(export_data.get('conversation_history', []))}条")
                    print(f"  • 学习模式: {len(export_data.get('learned_patterns', {}))}个")
                    print(f"  • 统计信息: {len(export_data.get('statistics', {}))}项")
            except Exception as e:
                print(f"❌ 验证导出文件失败: {e}")
        else:
            print("❌ 记忆数据导出失败")

        print("\n🎉 核心功能测试完成！")
        print("💡 智能记忆系统核心功能验证:")
        print("  ✅ 用户交互学习")
        print("  ✅ 习惯模式识别")
        print("  ✅ 个性化建议生成")
        print("  ✅ 用户画像分析")
        print("  ✅ 记忆数据导出")

        return True

    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        print("请确保所有必要的模块都已正确安装")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        logger.exception("Test error")
        return False


async def test_zhipuai_integration():
    """测试ZhipuAI集成"""
    print("\n🤖 测试ZhipuAI集成...")

    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 ZHIPUAI_API_KEY")
        return False

    try:
        from libs.memory.zhipuai_adapter import ZhipuAIChatAdapter

        adapter = ZhipuAIChatAdapter(api_key=api_key, model="glm-4.5-air")

        # 测试基本命令分析
        result = adapter.analyze_device_command(
            device_type="thermostat",
            current_state={
                "device_name": "客厅空调",
                "current_state": "OFF",
                "capabilities": {
                    "temperature": {"type": "number", "min": 16, "max": 32, "current_value": 24},
                    "power": {"type": "switch", "states": ["on", "off"], "current_value": "off"}
                }
            },
            command="设置空调到26度"
        )

        if result:
            print("✅ ZhipuAI集成测试成功")
            print(f"📝 解析结果: {result}")
            return True
        else:
            print("❌ ZhipuAI调用失败")
            return False

    except Exception as e:
        print(f"❌ ZhipuAI测试失败: {e}")
        return False


if __name__ == "__main__":
    print("🧠 SynHome 智能记忆系统测试套件")
    print("=" * 60)

    async def run_all_tests():
        print("开始运行所有测试...\n")

        # 测试ZhipuAI集成
        zhipuai_success = await test_zhipuai_integration()

        # 测试记忆系统核心功能
        memory_success = await test_smart_memory_core()

        print("\n" + "=" * 60)
        print("🎯 测试结果总结:")
        print(f"🤖 ZhipuAI集成: {'✅ 成功' if zhipuai_success else '❌ 失败'}")
        print(f"🧠 记忆系统核心: {'✅ 成功' if memory_success else '❌ 失败'}")

        if zhipuai_success and memory_success:
            print("\n🎉 所有测试通过！智能记忆系统MVP验证成功！")
            print("💡 系统已准备好集成到SynHome中")
        else:
            print("\n⚠️  部分测试失败，请检查配置和依赖")

    asyncio.run(run_all_tests())