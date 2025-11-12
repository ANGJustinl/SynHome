#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SynHome 自动化测试运行器
在单独线程中启动模拟服务器，然后运行测试
"""

import asyncio
import threading
import time
import sys
import os
import socket
import subprocess
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)

class MockServerThread:
    """在单独线程中运行的模拟服务器"""

    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws"
        self.server_process = None
        self.is_running = False
        self.startup_timeout = 15  # 15秒启动超时

    def is_port_available(self) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex((self.host, self.port))
                return result != 0
        except:
            return True

    def start_server(self):
        """启动模拟服务器"""
        if not self.is_port_available():
            logger.error(f"端口 {self.port} 已被占用")
            return False

        try:
            logger.info(f"🚀 启动模拟服务器在端口 {self.port}")

            # 在子进程中启动服务器
            cmd = [
                sys.executable, "-m", "uv", "run", "python",
                "device_mock_server.py", "--port", str(self.port)
            ]

            self.server_process = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(__file__),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            self.is_running = True

            # 等待服务器启动
            if self._wait_for_startup():
                logger.info(f"✅ 模拟服务器启动成功: {self.base_url}")
                return True
            else:
                logger.error("❌ 模拟服务器启动超时")
                self.stop_server()
                return False

        except Exception as e:
            logger.error(f"❌ 启动模拟服务器失败: {e}")
            return False

    def _wait_for_startup(self) -> bool:
        """等待服务器启动完成"""
        start_time = time.time()

        while time.time() - start_time < self.startup_timeout:
            if not self.server_process or self.server_process.poll() is not None:
                logger.error("服务器进程意外退出")
                return False

            # 检查服务器是否响应
            try:
                import aiohttp
                import asyncio

                # 在事件循环中检查服务器响应
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def check_server():
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(f"{self.base_url}/devices", timeout=5) as response:
                                return response.status == 200
                    except:
                        return False

                result = loop.run_until_complete(check_server())
                loop.close()

                if result:
                    return True

            except:
                pass

            time.sleep(0.5)

        return False

    def stop_server(self):
        """停止模拟服务器"""
        if self.server_process:
            try:
                logger.info("🛑 正在停止模拟服务器...")
                self.server_process.terminate()

                # 等待进程退出
                try:
                    self.server_process.wait(timeout=5)
                    logger.info("✅ 模拟服务器已停止")
                except subprocess.TimeoutExpired:
                    logger.warning("⚠️ 服务器未正常退出，强制终止")
                    self.server_process.kill()
                    self.server_process.wait()

            except Exception as e:
                logger.error(f"❌ 停止服务器时出错: {e}")
            finally:
                self.is_running = False
                self.server_process = None

class AutomatedTestRunner:
    """自动化测试运行器"""

    def __init__(self, server_port: int = 8000):
        self.server = MockServerThread(port=server_port)
        self.test_results = {}

    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        logger.info("🚀 开始SynHome自动化测试")
        logger.info("=" * 60)

        results = {
            "server_startup": False,
            "device_client_tests": False,
            "integration_tests": False,
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "success_rate": 0.0
            }
        }

        try:
            # 1. 启动模拟服务器
            logger.info("\n📡 步骤1: 启动模拟服务器")
            if not self.server.start_server():
                logger.error("❌ 无法启动模拟服务器，测试终止")
                return results
            results["server_startup"] = True

            # 等待服务器完全启动
            await asyncio.sleep(2)

            # 2. 运行设备客户端测试
            logger.info("\n🔌 步骤2: 运行设备客户端测试")
            device_results = await self.run_device_client_tests()
            results["device_client_tests"] = device_results["success"]

            # 3. 运行集成测试
            logger.info("\n🏢 步骤3: 运行集成测试")
            integration_results = await self.run_integration_tests()
            results["integration_tests"] = integration_results["success"]

            # 4. 计算总结
            results["summary"]["total_tests"] = len([r for r in results.values() if isinstance(r, bool)])
            results["summary"]["passed"] = sum(1 for r in results.values() if r is True)
            results["summary"]["failed"] = sum(1 for r in results.values() if r is False)
            results["summary"]["success_rate"] = (
                results["summary"]["passed"] / results["summary"]["total_tests"] * 100
                if results["summary"]["total_tests"] > 0 else 0
            )

        except Exception as e:
            logger.error(f"❌ 测试运行过程中出现错误: {e}")
            logger.exception("Test execution error")

        finally:
            # 5. 停止服务器
            logger.info("\n🛑 步骤5: 清理和停止服务器")
            self.server.stop_server()

        return results

    async def run_device_client_tests(self) -> Dict[str, Any]:
        """运行设备客户端测试"""
        try:
            # 导入测试客户端
            from test_device_client import DeviceTestClient, test_http_api, test_websocket_api, test_concurrent_operations

            logger.info("🧪 运行设备客户端测试...")

            all_results = {"success": True, "details": {}}

            # 更新服务器URL
            DeviceTestClient.server_url = self.server.base_url

            # 测试HTTP API
            logger.info("\n📡 测试HTTP API")
            http_results = await test_http_api()
            all_results["details"]["http_api"] = http_results
            if http_results["fail"] > 0:
                all_results["success"] = False

            await asyncio.sleep(1)

            # 测试WebSocket API
            logger.info("\n📡 测试WebSocket API")
            ws_results = await test_websocket_api()
            all_results["details"]["websocket_api"] = ws_results
            if ws_results["fail"] > 0:
                all_results["success"] = False

            await asyncio.sleep(1)

            # 测试并发操作
            logger.info("\n📡 测试并发操作")
            concurrent_results = await test_concurrent_operations()
            all_results["details"]["concurrent_operations"] = concurrent_results
            if concurrent_results["fail"] > 0:
                all_results["success"] = False

            return all_results

        except Exception as e:
            logger.error(f"❌ 设备客户端测试失败: {e}")
            return {"success": False, "error": str(e)}

    async def run_integration_tests(self) -> Dict[str, Any]:
        """运行集成测试"""
        try:
            from test_integration import (
                test_http_device_integration,
                test_device_manager_integration,
                test_smart_device_manager_integration,
                check_server_availability
            )

            logger.info("🧪 运行集成测试...")

            # 检查服务器可用性
            logger.info("🔍 检查模拟服务器可用性...")
            if not await check_server_availability():
                return {"success": False, "error": "模拟服务器不可用"}

            tests = [
                ("HTTP设备集成", test_http_device_integration),
                ("设备管理器集成", test_device_manager_integration),
                ("智能设备管理器集成", test_smart_device_manager_integration)
            ]

            results = {"success": True, "details": {}}

            for test_name, test_func in tests:
                logger.info(f"\n{'='*20} {test_name} {'='*20}")
                try:
                    result = await test_func()
                    results["details"][test_name] = {"success": result}
                    if not result:
                        results["success"] = False
                except Exception as e:
                    logger.error(f"❌ {test_name} 测试出现异常: {e}")
                    results["details"][test_name] = {"success": False, "error": str(e)}
                    results["success"] = False

                await asyncio.sleep(1)  # 测试间隔

            return results

        except Exception as e:
            logger.error(f"❌ 集成测试失败: {e}")
            return {"success": False, "error": str(e)}

    def print_results(self, results: Dict[str, Any]):
        """打印测试结果"""
        print("\n" + "=" * 60)
        print("🎯 SynHome自动化测试总结")
        print("=" * 60)

        # 步骤结果
        steps = [
            ("模拟服务器启动", results["server_startup"]),
            ("设备客户端测试", results["device_client_tests"]),
            ("集成测试", results["integration_tests"])
        ]

        for step_name, success in steps:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"   {step_name}: {status}")

        # 统计信息
        summary = results["summary"]
        print(f"\n📊 统计信息:")
        print(f"   总测试数: {summary['total_tests']}")
        print(f"   通过数: {summary['passed']}")
        print(f"   失败数: {summary['failed']}")
        print(f"   成功率: {summary['success_rate']:.1f}%")

        # 详细结果
        if "device_client_tests" in results and isinstance(results["device_client_tests"], dict):
            print(f"\n📡 设备客户端测试详情:")
            client_tests = results["device_client_tests"]
            if "details" in client_tests:
                for test_name, result in client_tests["details"].items():
                    if isinstance(result, dict) and "success" in result:
                        status = "✅" if result["success"] else "❌"
                        print(f"   {test_name}: {status}")

        if "integration_tests" in results and isinstance(results["integration_tests"], dict):
            print(f"\n🏢 集成测试详情:")
            integration_tests = results["integration_tests"]
            if "details" in integration_tests:
                for test_name, result in integration_tests["details"].items():
                    if isinstance(result, dict) and "success" in result:
                        status = "✅" if result["success"] else "❌"
                        error_info = f" - {result.get('error', '')}" if not result["success"] else ""
                        print(f"   {test_name}: {status}{error_info}")

        # 总体评估
        if summary["success_rate"] >= 90:
            print(f"\n🎉 测试结果优秀！系统运行良好！")
        elif summary["success_rate"] >= 70:
            print(f"\n⚠️ 大部分测试通过，系统基本正常")
        else:
            print(f"\n❌ 测试失败较多，需要检查系统")

async def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 创建测试运行器
    runner = AutomatedTestRunner(server_port=8000)

    try:
        # 运行所有测试
        results = await runner.run_all_tests()

        # 打印结果
        runner.print_results(results)

        # 返回适当的退出码
        exit_code = 0 if results["summary"]["success_rate"] >= 70 else 1
        return exit_code

    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
        runner.server.stop_server()
        return 1
    except Exception as e:
        print(f"\n❌ 测试运行器出现错误: {e}")
        runner.server.stop_server()
        return 1

if __name__ == "__main__":
    # 运行测试并返回退出码
    exit_code = asyncio.run(main())
    sys.exit(exit_code)