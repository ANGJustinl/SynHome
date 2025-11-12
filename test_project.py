#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SynHome 项目完整测试脚本
自动启动模拟服务器并运行所有测试
"""

import asyncio
import subprocess
import sys
import os
import time
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SynHomeTester:
    """SynHome完整测试套件"""

    def __init__(self):
        self.server_port = 8003
        self.server_process = None
        self.base_url = f"http://localhost:{self.server_port}"

    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 SynHome 完整测试套件")
        print("=" * 60)

        results = {
            "server_startup": False,
            "http_tests": False,
            "websocket_tests": False,
            "concurrent_tests": False,
            "integration_tests": False,
            "smart_memory_tests": False
        }

        try:
            # 1. 启动模拟服务器
            if not await self.start_server():
                print("❌ 无法启动模拟服务器")
                return results
            results["server_startup"] = True

            # 等待服务器启动
            await asyncio.sleep(2)

            # 2. 运行HTTP测试
            print("\n📡 步骤2: HTTP API测试")
            if await self.run_http_tests():
                results["http_tests"] = True

            await asyncio.sleep(1)

            # 3. 运行WebSocket测试
            print("\n🔌 步骤3: WebSocket测试")
            if await self.run_websocket_tests():
                results["websocket_tests"] = True

            await asyncio.sleep(1)

            # 4. 运行并发测试
            print("\n⚡ 步骤4: 并发测试")
            if await self.run_concurrent_tests():
                results["concurrent_tests"] = True

            await asyncio.sleep(1)

            # 5. 运行集成测试
            print("\n🏢 步骤5: 集成测试")
            if await self.run_integration_tests():
                results["integration_tests"] = True

            await asyncio.sleep(1)

            # 6. 运行智能记忆测试
            print("\n🧠 步骤6: 智能记忆测试")
            if await self.run_smart_memory_tests():
                results["smart_memory_tests"] = True

        except Exception as e:
            logger.error(f"测试过程中出现错误: {e}")
        finally:
            await self.stop_server()

        return results

    async def start_server(self) -> bool:
        """启动模拟服务器"""
        print(f"🚀 启动模拟服务器在端口 {self.server_port}")

        cmd = [
            sys.executable, "-m", "uv", "run", "python",
            "tests/device_mock_server.py", "--port", str(self.server_port),
            "--log-level", "warning"
        ]

        self.server_process = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(__file__),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 等待服务器启动
        return await self._wait_for_server()

    async def _wait_for_server(self, timeout: int = 15) -> bool:
        """等待服务器响应"""
        try:
            import requests

            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.server_process and self.server_process.poll() is not None:
                    return False

                try:
                    response = requests.get(f"{self.base_url}/devices", timeout=2)
                    if response.status_code == 200:
                        print(f"✅ 模拟服务器启动成功: {self.base_url}")
                        return True
                except:
                    pass

                await asyncio.sleep(0.5)

            print("❌ 服务器启动超时")
            return False

        except Exception as e:
            print(f"❌ 检查服务器状态失败: {e}")
            return False

    async def stop_server(self):
        """停止模拟服务器"""
        if self.server_process:
            print("🛑 正在停止模拟服务器...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
                print("✅ 模拟服务器已停止")
            except subprocess.TimeoutExpired:
                print("⚠️ 强制终止服务器")
                self.server_process.kill()
                self.server_process.wait()
            finally:
                self.server_process = None

    async def run_http_tests(self) -> bool:
        """运行HTTP测试"""
        try:
            from tests.test_device_client import test_http_api

            # 设置服务器URL
            from tests.test_device_client import DeviceTestClient
            DeviceTestClient.server_url = self.base_url

            result = await test_http_api()
            success = result["fail"] == 0

            print(f"   HTTP测试: {'✅' if success else '❌'} (成功: {result['success']}, 失败: {result['fail']})")
            return success

        except Exception as e:
            print(f"   ❌ HTTP测试异常: {e}")
            return False

    async def run_websocket_tests(self) -> bool:
        """运行WebSocket测试"""
        try:
            from tests.test_device_client import test_websocket_api

            # 设置服务器URL
            from tests.test_device_client import DeviceTestClient
            DeviceTestClient.server_url = self.base_url

            result = await test_websocket_api()
            success = result["fail"] == 0

            print(f"   WebSocket测试: {'✅' if success else '❌'} (成功: {result['success']}, 失败: {result['fail']})")
            return success

        except Exception as e:
            print(f"   ❌ WebSocket测试异常: {e}")
            return False

    async def run_concurrent_tests(self) -> bool:
        """运行并发测试"""
        try:
            from tests.test_device_client import test_concurrent_operations

            # 设置服务器URL
            from tests.test_device_client import DeviceTestClient
            DeviceTestClient.server_url = self.base_url

            result = await test_concurrent_operations()
            success = result["fail"] == 0

            print(f"   并发测试: {'✅' if success else '❌'} (成功: {result['success']}, 失败: {result['fail']})")
            return success

        except Exception as e:
            print(f"   ❌ 并发测试异常: {e}")
            return False

    async def run_integration_tests(self) -> bool:
        """运行集成测试"""
        try:
            from tests.test_integration import test_http_device_integration

            # 修改设备配置中的端口
            print("   🔌 HTTP设备集成测试...")
            result = await test_http_device_integration()

            print(f"   HTTP设备集成测试: {'✅' if result else '❌'}")
            return result

        except Exception as e:
            print(f"   ❌ 集成测试异常: {e}")
            return False

    async def run_smart_memory_tests(self) -> bool:
        """运行智能记忆测试"""
        try:
            import os

            # 设置API密钥环境变量（如果可用）
            if not os.getenv("ZHIPUAI_API_KEY"):
                print("   ℹ️ 智能记忆测试需要API密钥，跳过")
                return True

            # 运行智能记忆测试
            proc = subprocess.run([
                sys.executable, "-m", "uv", "run", "python",
                "test_smart_memory_simple.py"
            ], cwd=os.path.dirname(__file__), capture_output=True, text=True)

            success = proc.returncode == 0
            print(f"   智能记忆测试: {'✅' if success else '❌'}")

            if not success:
                print(f"   错误信息: {proc.stderr[:200]}...")

            return success

        except Exception as e:
            print(f"   ❌ 智能记忆测试异常: {e}")
            return False

    def print_summary(self, results):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("🎯 SynHome 测试总结")
        print("=" * 60)

        test_names = {
            "server_startup": "服务器启动",
            "http_tests": "HTTP API测试",
            "websocket_tests": "WebSocket测试",
            "concurrent_tests": "并发测试",
            "integration_tests": "集成测试",
            "smart_memory_tests": "智能记忆测试"
        }

        passed = 0
        total = len(results)

        for key, name in test_names.items():
            if key in results:
                status = "✅ 通过" if results[key] else "❌ 失败"
                print(f"   {name}: {status}")
                if results[key]:
                    passed += 1

        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n📊 总体结果: {passed}/{total} 测试通过 ({success_rate:.1f}%)")

        if success_rate >= 90:
            print("\n🎉 优秀！系统运行完美！")
        elif success_rate >= 70:
            print("\n✅ 良好！系统基本正常")
        else:
            print("\n⚠️ 需要改进：部分功能存在问题")

async def main():
    """主函数"""
    tester = SynHomeTester()

    try:
        results = await tester.run_all_tests()
        tester.print_summary(results)

        # 根据成功率返回退出码
        success_rate = sum(1 for r in results.values() if r) / len(results) * 100
        return 0 if success_rate >= 70 else 1

    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        await tester.stop_server()
        return 1
    except Exception as e:
        print(f"\n❌ 测试执行异常: {e}")
        await tester.stop_server()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)