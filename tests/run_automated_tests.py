#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SynHome 自动化测试入口
在单独线程中启动模拟服务器并运行测试
"""

import asyncio
import sys
import os
import logging
import subprocess
import time
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MockServerManager:
    """模拟服务器管理器"""

    def __init__(self, port: int = 8000):
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.process = None
        self.is_running = False

    def start(self) -> bool:
        """启动服务器"""
        try:
            print(f"🚀 启动模拟服务器在端口 {self.port}")

            # 启动服务器进程
            cmd = [
                sys.executable, "device_mock_server.py", "--port", str(self.port)
            ]

            self.process = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(__file__),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 等待服务器启动
            if self._wait_for_server():
                print(f"✅ 模拟服务器启动成功: {self.base_url}")
                self.is_running = True
                return True
            else:
                print("❌ 模拟服务器启动失败")
                self.stop()
                return False

        except Exception as e:
            print(f"❌ 启动模拟服务器异常: {e}")
            return False

    def _wait_for_server(self, timeout: int = 15) -> bool:
        """等待服务器响应"""
        import requests

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.process and self.process.poll() is not None:
                return False

            try:
                response = requests.get(f"{self.base_url}/devices", timeout=2)
                if response.status_code == 200:
                    return True
            except:
                pass

            time.sleep(0.5)
        return False

    def stop(self):
        """停止服务器"""
        if self.process:
            print("🛑 正在停止模拟服务器...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                print("✅ 模拟服务器已停止")
            except subprocess.TimeoutExpired:
                print("⚠️ 强制终止服务器")
                self.process.kill()
                self.process.wait()
            finally:
                self.is_running = False
                self.process = None

async def run_device_tests(server_url: str) -> Dict[str, Any]:
    """运行设备测试"""
    print(f"🔌 开始设备测试: {server_url}")

    try:
        # 设置设备客户端的默认URL
        from test_device_client import DeviceTestClient
        DeviceTestClient.server_url = server_url

        # 运行基本测试
        async with DeviceTestClient() as client:
            # 测试获取设备列表
            devices_response = await client.get_all_devices()
            if not devices_response:
                return {"success": False, "error": "无法获取设备列表"}

            device_count = len(devices_response.get("devices", []))
            print(f"✅ 成功获取 {device_count} 个设备")

            # 测试第一个设备的操作
            if device_count > 0:
                first_device = devices_response["devices"][0]
                device_id = first_device["device_id"]
                device_type = first_device["device_type"]

                print(f"🎮 测试设备操作: {device_id} ({device_type})")

                # 测试电源开关
                result = await client.send_command(device_id, "power", "on")
                if result.get("success"):
                    print("   ✅ 电源开启成功")

                    await asyncio.sleep(0.5)

                    result = await client.send_command(device_id, "power", "off")
                    if result.get("success"):
                        print("   ✅ 电源关闭成功")
                        return {"success": True, "devices_tested": 1}
                    else:
                        print("   ❌ 电源关闭失败")
                        return {"success": False, "error": "电源关闭失败"}
                else:
                    print("   ❌ 电源开启失败")
                    return {"success": False, "error": "电源开启失败"}

            return {"success": True, "devices_tested": 0}

    except Exception as e:
        print(f"❌ 设备测试异常: {e}")
        return {"success": False, "error": str(e)}

async def main():
    """主函数"""
    print("🚀 SynHome自动化测试")
    print("=" * 50)

    server_port = 8002
    server_manager = MockServerManager(server_port)

    try:
        # 启动服务器
        if not server_manager.start():
            print("❌ 无法启动服务器，测试终止")
            return 1

        await asyncio.sleep(1)

        # 运行测试
        test_results = await run_device_tests(server_manager.base_url)

        if test_results["success"]:
            print(f"\n🎉 测试成功完成！")
            print(f"   测试设备数量: {test_results.get('devices_tested', 0)}")
            return 0
        else:
            print(f"\n❌ 测试失败: {test_results.get('error')}")
            return 1

    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 测试执行异常: {e}")
        return 1
    finally:
        # 清理
        server_manager.stop()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)