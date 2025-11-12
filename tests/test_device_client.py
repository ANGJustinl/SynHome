#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SynHome 设备客户端测试器
用于测试HTTP和WebSocket设备交互
"""

import asyncio
import json
import logging
import time
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import aiohttp
import websockets

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeviceTestClient:
    """设备测试客户端"""

    def __init__(self, server_url: str = None):
        # 支持类级别的默认URL和实例级别的覆盖
        if server_url is None:
            server_url = getattr(DeviceTestClient, 'server_url', "http://localhost:8000")

        self.server_url = server_url
        self.ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        self.session = None
        self.websocket = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()

    async def connect(self):
        """连接到服务器"""
        self.session = aiohttp.ClientSession()
        logger.info("✅ HTTP客户端已连接")

    async def connect_websocket(self):
        """连接WebSocket"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.info("✅ WebSocket客户端已连接")
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket连接失败: {e}")
            return False

    async def disconnect(self):
        """断开所有连接"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("🔌 WebSocket已断开")

        if self.session:
            await self.session.close()
            self.session = None
            logger.info("🔌 HTTP已断开")

    # HTTP API 测试方法
    async def get_all_devices(self) -> Dict[str, Any]:
        """获取所有设备"""
        try:
            async with self.session.get(f"{self.server_url}/devices") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"获取设备列表失败: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"获取设备列表异常: {e}")
            return {}

    async def get_device(self, device_id: str) -> Dict[str, Any]:
        """获取单个设备"""
        try:
            async with self.session.get(f"{self.server_url}/devices/{device_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"获取设备{device_id}失败: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"获取设备{device_id}异常: {e}")
            return {}

    async def send_command(self, device_id: str, capability: str, value: Any) -> Dict[str, Any]:
        """发送设备命令"""
        try:
            command_data = {
                "device_id": device_id,
                "capability": capability,
                "value": value,
                "timestamp": datetime.now().isoformat()
            }

            async with self.session.post(
                f"{self.server_url}/devices/{device_id}/command",
                json=command_data
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"发送命令失败: {response.status} - {error_text}")
                    return {"success": False, "error": error_text}
        except Exception as e:
            logger.error(f"发送命令异常: {e}")
            return {"success": False, "error": str(e)}

    # WebSocket 测试方法
    async def listen_websocket(self, duration: int = 30) -> List[Dict[str, Any]]:
        """监听WebSocket消息"""
        if not self.websocket:
            if not await self.connect_websocket():
                return []

        messages = []
        try:
            start_time = time.time()
            while time.time() - start_time < duration:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    data["received_time"] = datetime.now().isoformat()
                    messages.append(data)
                    logger.info(f"📨 收到WebSocket消息: {data.get('type', 'unknown')}")
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            logger.error(f"WebSocket监听错误: {e}")

        return messages

    async def send_websocket_ping(self):
        """发送WebSocket ping"""
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({"type": "ping"}))
                logger.info("📤 发送ping消息")
            except Exception as e:
                logger.error(f"发送ping失败: {e}")

# 测试用例
async def test_http_api():
    """测试HTTP API"""
    logger.info("🧪 开始测试HTTP API")
    results = {"success": 0, "fail": 0}

    async with DeviceTestClient() as client:
        # 测试获取所有设备
        logger.info("1️⃣ 测试获取所有设备")
        devices_response = await client.get_all_devices()
        if devices_response and "devices" in devices_response:
            devices = devices_response["devices"]
            logger.info(f"✅ 成功获取 {len(devices)} 个设备")
            results["success"] += 1

            # 打印设备信息
            for device in devices:
                logger.info(f"   📱 {device['device_id']}: {device['name']} ({device['device_type']})")
        else:
            logger.error("❌ 获取设备列表失败")
            results["fail"] += 1
            return results

        # 测试单个设备操作
        if devices:
            test_device = devices[0]
            device_id = test_device["device_id"]
            device_type = test_device["device_type"]

            logger.info(f"2️⃣ 测试设备 {device_id} ({device_type})")

            # 测试获取单个设备
            device_info = await client.get_device(device_id)
            if device_info:
                logger.info("✅ 成功获取设备信息")
                results["success"] += 1
            else:
                logger.error("❌ 获取设备信息失败")
                results["fail"] += 1

            # 测试设备命令
            if device_type == "thermostat":
                commands = [
                    ("power", "on"),
                    ("temperature", 26),
                    ("mode", "cool"),
                    ("power", "off")
                ]
            elif device_type == "light":
                commands = [
                    ("power", "on"),
                    ("brightness", 80),
                    ("color", "warm"),
                    ("brightness", 30),
                    ("power", "off")
                ]
            else:
                commands = [("power", "on"), ("power", "off")]

            logger.info("3️⃣ 测试设备命令")
            for capability, value in commands:
                result = await client.send_command(device_id, capability, value)
                if result.get("success"):
                    logger.info(f"   ✅ 设置 {capability} = {value}")
                    results["success"] += 1
                else:
                    logger.error(f"   ❌ 设置 {capability} = {value} 失败: {result.get('error')}")
                    results["fail"] += 1

                # 短暂延迟模拟真实操作
                await asyncio.sleep(0.5)

            # 测试错误情况
            logger.info("4️⃣ 测试错误处理")
            error_result = await client.send_command(device_id, "invalid_capability", "invalid_value")
            if not error_result.get("success"):
                logger.info("✅ 错误处理正确")
                results["success"] += 1
            else:
                logger.error("❌ 错误处理有问题")
                results["fail"] += 1

    return results

async def test_websocket_api():
    """测试WebSocket API"""
    logger.info("🧪 开始测试WebSocket API")
    results = {"success": 0, "fail": 0}

    async with DeviceTestClient() as client:
        # 连接WebSocket
        if not await client.connect_websocket():
            logger.error("❌ WebSocket连接失败")
            results["fail"] += 1
            return results

        results["success"] += 1

        # 启动消息监听任务
        listen_task = asyncio.create_task(client.listen_websocket(duration=20))

        # 等待一下让初始状态到达
        await asyncio.sleep(2)

        # 发送一些命令来触发WebSocket消息
        logger.info("📤 发送测试命令以触发WebSocket消息")

        devices_response = await client.get_all_devices()
        if devices_response and "devices" in devices_response:
            devices = devices_response["devices"]
            if devices:
                test_device = devices[1]  # 使用第二个设备
                device_id = test_device["device_id"]

                # 发送几个命令
                await client.send_command(device_id, "power", "on")
                await asyncio.sleep(1)
                await client.send_command(device_id, "power", "off")
                await asyncio.sleep(1)

                # 测试ping
                await client.send_websocket_ping()

        # 等待监听完成
        messages = await listen_task

        # 分析收到的消息
        logger.info(f"📨 收到 {len(messages)} 条WebSocket消息")
        message_types = [msg.get("type") for msg in messages]
        logger.info(f"📋 消息类型: {set(message_types)}")

        # 检查关键消息类型
        expected_types = ["initial_state", "device_state_change", "pong"]
        received_types = set(message_types)

        for msg_type in expected_types:
            if msg_type in received_types:
                logger.info(f"   ✅ 收到预期消息类型: {msg_type}")
                results["success"] += 1
            else:
                logger.error(f"   ❌ 未收到预期消息类型: {msg_type}")
                results["fail"] += 1

        # 打印一些消息示例
        if messages:
            logger.info("📋 消息示例:")
            for i, msg in enumerate(messages[:3]):
                logger.info(f"   {i+1}. {msg.get('type')}: {json.dumps(msg, ensure_ascii=False)}")

    return results

async def test_concurrent_operations():
    """测试并发操作"""
    logger.info("🧪 开始测试并发操作")

    async def device_operator(device_id: str, operator_id: int):
        """设备操作器"""
        results = {"success": 0, "fail": 0}

        async with DeviceTestClient() as client:
            commands = [
                ("power", "on"),
                ("power", "off")
            ]

            for i in range(5):  # 每个操作器执行5次循环
                for capability, value in commands:
                    result = await client.send_command(device_id, capability, value)
                    if result.get("success"):
                        results["success"] += 1
                    else:
                        results["fail"] += 1

                    await asyncio.sleep(0.1)

        logger.info(f"操作器 {operator_id}: 成功 {results['success']}, 失败 {results['fail']}")
        return results

    # 获取设备列表
    async with DeviceTestClient() as client:
        devices_response = await client.get_all_devices()
        if not devices_response or "devices" not in devices_response:
            logger.error("❌ 无法获取设备列表")
            return {"success": 0, "fail": 1}

        devices = devices_response["devices"]
        if len(devices) < 2:
            logger.error("❌ 设备数量不足")
            return {"success": 0, "fail": 1}

        # 创建并发的设备操作器
        tasks = [
            device_operator(devices[0]["device_id"], 1),
            device_operator(devices[1]["device_id"], 2)
        ]

        start_time = time.time()
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        # 统计结果
        total_success = sum(r.get("success", 0) for r in results_list if isinstance(r, dict))
        total_fail = sum(r.get("fail", 0) for r in results_list if isinstance(r, dict))

        logger.info(f"⏱️ 并发测试耗时: {end_time - start_time:.2f}秒")
        logger.info(f"✅ 总成功操作: {total_success}")
        logger.info(f"❌ 总失败操作: {total_fail}")

        return {"success": total_success, "fail": total_fail}

async def main():
    """主测试函数"""
    print("🚀 开始SynHome设备交互测试")
    print("=" * 60)

    total_results = {"success": 0, "fail": 0}

    # 测试1: HTTP API
    print("\n📡 测试1: HTTP API")
    http_results = await test_http_api()
    total_results["success"] += http_results["success"]
    total_results["fail"] += http_results["fail"]
    print(f"HTTP测试结果: ✅ {http_results['success']}  ❌ {http_results['fail']}")

    # 等待一下让系统稳定
    await asyncio.sleep(2)

    # 测试2: WebSocket API
    print("\n📡 测试2: WebSocket API")
    ws_results = await test_websocket_api()
    total_results["success"] += ws_results["success"]
    total_results["fail"] += ws_results["fail"]
    print(f"WebSocket测试结果: ✅ {ws_results['success']}  ❌ {ws_results['fail']}")

    # 等待一下让系统稳定
    await asyncio.sleep(2)

    # 测试3: 并发操作
    print("\n📡 测试3: 并发操作")
    concurrent_results = await test_concurrent_operations()
    total_results["success"] += concurrent_results["success"]
    total_results["fail"] += concurrent_results["fail"]
    print(f"并发测试结果: ✅ {concurrent_results['success']}  ❌ {concurrent_results['fail']}")

    # 总结
    print("\n" + "=" * 60)
    print("🎯 测试总结:")
    print(f"   总成功操作: {total_results['success']}")
    print(f"   总失败操作: {total_results['fail']}")
    success_rate = total_results['success'] / (total_results['success'] + total_results['fail']) * 100
    print(f"   成功率: {success_rate:.1f}%")

    if success_rate > 90:
        print("\n🎉 所有测试通过！设备交互系统工作正常！")
    elif success_rate > 70:
        print("\n⚠️  大部分测试通过，但有一些问题需要检查")
    else:
        print("\n❌ 测试失败较多，请检查系统配置")

    print("\n💡 提示:")
    print("   - 确保模拟服务器正在运行 (python tests/device_mock_server.py)")
    print("   - 检查防火墙设置")
    print("   - 查看服务器日志以获取更多错误信息")

if __name__ == "__main__":
    asyncio.run(main())