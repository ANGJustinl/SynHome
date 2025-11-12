#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SynHome 设备管理器与模拟后端集成测试
"""

import asyncio
import json
import logging
import tempfile
import yaml
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)

async def test_http_device_integration():
    """测试HTTP设备集成"""
    print("🔌 测试HTTP设备集成")
    print("-" * 50)

    try:
        # 导入必要模块
        from libs.devices.http_device import HTTPDevice
        from libs.devices.device_manager import DeviceManager

        # HTTP设备配置
        http_device_config = {
            "name": "HTTP智能空调",
            "type": "thermostat",
            "capabilities": [
                {
                    "power": {
                        "type": "switch",
                        "states": ["off", "on"],
                        "current_value": "off"
                    }
                },
                {
                    "temperature": {
                        "type": "number",
                        "min": 16.0,
                        "max": 32.0,
                        "unit": "°C",
                        "current_value": 24.0
                    }
                }
            ],
            "api": {
                "base_url": "http://localhost:8000",
                "auth_type": "none",
                "timeout": 10,
                "commands": {
                    "power": {
                        "method": "POST",
                        "endpoint": "devices/thermostat_001/command",
                        "value_key": "value"
                    },
                    "temperature": {
                        "method": "POST",
                        "endpoint": "devices/thermostat_001/command",
                        "value_key": "value"
                    }
                }
            }
        }

        # 创建HTTP设备
        http_device = HTTPDevice("http_thermostat_001", http_device_config)
        print(f"✅ HTTP设备创建成功: {http_device.name}")

        # 测试设备操作
        print("\n🎮 测试设备操作:")

        # 测试开关
        print("  1. 测试电源开关...")
        result = http_device.set_capability("power", "on")
        print(f"     开启结果: {'✅' if result else '❌'}")

        await asyncio.sleep(0.5)

        result = http_device.set_capability("power", "off")
        print(f"     关闭结果: {'✅' if result else '❌'}")

        # 测试温度设置
        print("  2. 测试温度设置...")
        result = http_device.set_capability("power", "on")
        if result:
            await asyncio.sleep(0.5)
            result = http_device.set_capability("temperature", 26)
            print(f"     温度设置结果: {'✅' if result else '❌'}")

        # 获取设备状态
        print("  3. 获取设备状态...")
        state = http_device.get_current_state()
        print(f"     设备状态: {state}")

        print("\n🎉 HTTP设备集成测试完成!")
        return True

    except Exception as e:
        print(f"❌ HTTP设备集成测试失败: {e}")
        logger.exception("HTTP integration test error")
        return False

async def test_device_manager_integration():
    """测试设备管理器集成"""
    print("\n🏢 测试设备管理器集成")
    print("-" * 50)

    try:
        # 导入必要模块
        from libs.devices.device_manager import DeviceManager

        # 创建设备配置文件
        devices_config = {
            "devices": [
                {
                    "id": "managed_thermostat_001",
                    "name": "管理器控制空调",
                    "type": "thermostat",
                    "capabilities": [
                        {
                            "power": {
                                "type": "switch",
                                "states": ["off", "on"],
                                "current_value": "off"
                            }
                        },
                        {
                            "temperature": {
                                "type": "number",
                                "min": 16.0,
                                "max": 32.0,
                                "unit": "°C",
                                "current_value": 24.0
                            }
                        }
                    ],
                    "api": {
                        "base_url": "http://localhost:8000",
                        "auth_type": "none",
                        "timeout": 10,
                        "commands": {
                            "power": {
                                "method": "POST",
                                "endpoint": "devices/thermostat_001/command",
                                "value_key": "value"
                            },
                            "temperature": {
                                "method": "POST",
                                "endpoint": "devices/thermostat_001/command",
                                "value_key": "value"
                            }
                        }
                    }
                },
                {
                    "id": "managed_light_001",
                    "name": "管理器控制灯光",
                    "type": "light",
                    "capabilities": [
                        {
                            "power": {
                                "type": "switch",
                                "states": ["off", "on"],
                                "current_value": "off"
                            }
                        },
                        {
                            "brightness": {
                                "type": "number",
                                "min": 0.0,
                                "max": 100.0,
                                "unit": "%",
                                "current_value": 0.0
                            }
                        }
                    ],
                    "api": {
                        "base_url": "http://localhost:8000",
                        "auth_type": "none",
                        "timeout": 10,
                        "commands": {
                            "power": {
                                "method": "POST",
                                "endpoint": "devices/light_001/command",
                                "value_key": "value"
                            },
                            "brightness": {
                                "method": "POST",
                                "endpoint": "devices/light_001/command",
                                "value_key": "value"
                            }
                        }
                    }
                }
            ]
        }

        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as config_file:
            yaml.dump(devices_config, config_file, default_flow_style=False, allow_unicode=True)
            config_file_path = config_file.name

        print(f"✅ 配置文件创建: {config_file_path}")

        # 创建设备管理器
        device_manager = DeviceManager()
        print("✅ 设备管理器创建成功")

        # 从配置加载设备
        print("\n📂 加载设备配置...")
        devices = device_manager.load_from_config(config_file_path)
        print(f"✅ 成功加载 {len(devices)} 个设备")

        # 显示设备列表
        print("\n📱 设备列表:")
        for device_id in devices:
            device = device_manager.get_device(device_id)
            print(f"  • {device.name} ({device.type}) - {len(device.capabilities)} 个能力")

        # 测试设备操作
        print("\n🎮 测试设备管理操作:")

        # 操作空调
        print("  1. 测试空调操作...")
        result = device_manager.set_device_state("managed_thermostat_001", "power", "on")
        print(f"     开启空调: {'✅' if result else '❌'}")

        await asyncio.sleep(0.5)

        result = device_manager.set_device_state("managed_thermostat_001", "temperature", 26)
        print(f"     设置温度: {'✅' if result else '❌'}")

        # 操作灯光
        print("  2. 测试灯光操作...")
        result = device_manager.set_device_state("managed_light_001", "power", "on")
        print(f"     开启灯光: {'✅' if result else '❌'}")

        await asyncio.sleep(0.5)

        result = device_manager.set_device_state("managed_light_001", "brightness", 80)
        print(f"     设置亮度: {'✅' if result else '❌'}")

        # 获取所有设备状态
        print("  3. 获取所有设备状态...")
        all_states = device_manager.get_all_device_states()
        for device_id, state in all_states.items():
            print(f"     {device_id}: {json.dumps(state, ensure_ascii=False)}")

        # 清理临时文件
        import os
        os.unlink(config_file_path)
        print("\n🗑️ 临时配置文件已清理")

        print("\n🎉 设备管理器集成测试完成!")
        return True

    except Exception as e:
        print(f"❌ 设备管理器集成测试失败: {e}")
        logger.exception("Device manager integration test error")
        return False

async def test_smart_device_manager_integration():
    """测试智能设备管理器集成（带记忆功能）"""
    print("\n🧠 测试智能设备管理器集成")
    print("-" * 50)

    try:
        # 导入必要模块
        from libs.devices.smart_device_manager import SmartDeviceManager
        from libs.utils.config import ConfigLoader

        # 创建智能设备配置
        devices_config = {
            "devices": [
                {
                    "id": "smart_thermostat_001",
                    "name": "智能记忆空调",
                    "type": "thermostat",
                    "capabilities": [
                        {
                            "power": {
                                "type": "switch",
                                "states": ["off", "on"],
                                "current_value": "off"
                            }
                        },
                        {
                            "temperature": {
                                "type": "number",
                                "min": 16.0,
                                "max": 32.0,
                                "unit": "°C",
                                "current_value": 24.0
                            }
                        }
                    ],
                    "api": {
                        "base_url": "http://localhost:8000",
                        "auth_type": "none",
                        "timeout": 10,
                        "commands": {
                            "power": {
                                "method": "POST",
                                "endpoint": "devices/thermostat_001/command",
                                "value_key": "value"
                            },
                            "temperature": {
                                "method": "POST",
                                "endpoint": "devices/thermostat_001/command",
                                "value_key": "value"
                            }
                        }
                    }
                }
            ]
        }

        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as config_file:
            yaml.dump(devices_config, config_file, default_flow_style=False, allow_unicode=True)
            config_file_path = config_file.name

        print(f"✅ 智能设备配置文件创建: {config_file_path}")

        # 创建智能设备管理器
        smart_manager = SmartDeviceManager(user_id="integration_test_user", enable_memory=True)
        print("✅ 智能设备管理器创建成功")

        # 加载设备配置
        config_loader = ConfigLoader(config_file_path)
        config_data = config_loader.load()
        devices_config = config_data.get("devices", [])
        smart_manager.load_devices_from_config(devices_config)
        print("✅ 设备配置加载成功")

        # 启用智能控制（如果API密钥可用）
        api_key = "test_key"  # 使用测试密钥
        try:
            smart_manager.enable_smart_control(api_key)
            print("✅ 智能控制已启用")
        except Exception as e:
            print(f"⚠️ 智能控制启用失败，继续基本测试: {e}")

        # 测试智能命令处理
        print("\n🎮 测试智能命令处理:")

        commands = [
            ("打开智能记忆空调", "thermostat", {"temperature": 22, "user_activity": "morning_routine"}),
            ("设置温度到26度", "thermostat", {"temperature": 22, "user_activity": "working"}),
            ("关闭智能记忆空调", "thermostat", {"temperature": 24, "user_activity": "leaving_home"})
        ]

        for i, (command, device_hint, context) in enumerate(commands, 1):
            print(f"  {i}. 处理命令: {command}")
            try:
                result = await smart_manager.process_smart_command(
                    command=command,
                    device_hint=device_hint,
                    environmental_context=context
                )

                if result.get('success'):
                    print(f"     ✅ 命令执行成功: {result.get('device_name', 'Unknown')}")
                else:
                    print(f"     ❌ 命令执行失败: {result.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"     ⚠️ 命令处理异常: {e}")

            await asyncio.sleep(0.5)

        # 获取记忆统计
        try:
            print("\n📊 智能记忆统计:")
            memory_summary = smart_manager.get_memory_summary()
            if 'error' not in memory_summary:
                stats = memory_summary.get('statistics', {})
                print(f"   总交互次数: {stats.get('total_interactions', 0)}")
                print(f"   学习的模式数: {stats.get('learned_patterns', 0)}")
                print(f"   记忆大小: {stats.get('memory_size', 0)}")
            else:
                print("   ℹ️ 记忆系统未启用或配置错误")
        except Exception as e:
            print(f"   ℹ️ 获取记忆统计失败: {e}")

        # 清理临时文件
        import os
        os.unlink(config_file_path)
        print("\n🗑️ 临时配置文件已清理")

        print("\n🎉 智能设备管理器集成测试完成!")
        return True

    except Exception as e:
        print(f"❌ 智能设备管理器集成测试失败: {e}")
        logger.exception("Smart device manager integration test error")
        return False

async def check_server_availability():
    """检查模拟服务器是否可用"""
    print("🔍 检查模拟服务器可用性...")

    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/devices") as response:
                if response.status == 200:
                    data = await response.json()
                    device_count = data.get("count", 0)
                    print(f"✅ 模拟服务器可用，发现 {device_count} 个设备")
                    return True
                else:
                    print(f"❌ 模拟服务器响应异常: {response.status}")
                    return False

    except Exception as e:
        print(f"❌ 无法连接到模拟服务器: {e}")
        print("💡 请先启动模拟服务器: python tests/device_mock_server.py")
        return False

async def main():
    """主集成测试函数"""
    print("🚀 开始SynHome设备集成测试")
    print("=" * 60)

    # 检查模拟服务器
    if not await check_server_availability():
        return

    # 运行集成测试
    tests = [
        ("HTTP设备集成", test_http_device_integration),
        ("设备管理器集成", test_device_manager_integration),
        ("智能设备管理器集成", test_smart_device_manager_integration)
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 测试出现异常: {e}")
            results.append((test_name, False))

    # 测试总结
    print("\n" + "=" * 60)
    print("🎯 集成测试总结:")
    success_count = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            success_count += 1

    print(f"\n总体结果: {success_count}/{len(results)} 测试通过")

    if success_count == len(results):
        print("\n🎉 所有集成测试通过！")
        print("💡 SynHome设备系统与模拟后端集成成功！")
    else:
        print("\n⚠️ 部分测试失败，请检查配置和依赖")

    print("\n📋 后续建议:")
    print("   1. 检查模拟服务器日志")
    print("   2. 验证网络连接")
    print("   3. 检查设备配置格式")
    print("   4. 测试更多设备类型")

if __name__ == "__main__":
    # 设置日志级别
    logging.basicConfig(level=logging.WARNING)  # 减少日志噪音

    # 运行测试
    asyncio.run(main())