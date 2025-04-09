#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试复合命令功能
"""

import logging
import os
import sys
from pathlib import Path
from pprint import pprint

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from libs.utils.config import ConfigLoader
from libs.devices.device_manager import DeviceManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_compound_commands():
    """测试复合命令处理"""
    
    # 加载配置
    try:
        config = ConfigLoader("config/demo.yaml").load()
        api_key = config["zhipuai"]["api_key"]
        
        # 创建设备管理器
        device_manager = DeviceManager()
        
        # 加载设备
        device_manager.load_devices_from_config(config["devices"])
        device_manager.enable_llm_control(api_key)
        
        # 测试命令列表
        test_commands = [
            "打开客厅灯",
            "把客厅灯亮度调到30%",
            "打开灯并设置亮度为50%",
            "关灯",
            "打开空调，设置温度为26度",
            "开启窗帘，拉到一半",
            "开灯并调成阅读模式",
            "开始煮饭，选择标准模式"
        ]
        
        # 执行测试命令
        for cmd in test_commands:
            print(f"\n测试命令: {cmd}")
            result = device_manager.process_command(cmd)
            print(f"结果: {result}\n{'-'*50}")
            
    except Exception as e:
        logger.error(f"测试出错: {str(e)}", exc_info=True)

async def test_physical_devices():
    """测试物理设备控制功能"""
    
    # 加载配置
    try:
        config = ConfigLoader("config/demo.yaml").load()
        api_key = config["zhipuai"]["api_key"]
        
        # 创建设备管理器
        device_manager = DeviceManager()
        
        # 加载设备
        device_manager.load_devices_from_config(config["devices"])
        device_manager.enable_llm_control(api_key)
        
        # 初始化物理设备适配器
        if "adapters" in config:
            await device_manager.load_adapters_from_config(config["adapters"])
            print(f"Loaded {len(device_manager.adapters)} adapters")
            
            # 关联物理设备
            if "physical_devices" in config:
                await device_manager.associate_physical_devices(config["physical_devices"])
                print("Associated physical devices")
        
        # 测试与物理设备交互
        # 找到一个有适配器关联的设备
        for device in device_manager.get_all_devices():
            if hasattr(device, 'adapter_id') and device.adapter_id:
                print(f"Testing physical device: {device.name}")
                
                # 发送命令到物理设备
                command = {"command": "set_power", "params": {"power": "on"}}
                result = await device_manager.send_command_to_physical_device(device.id, command)
                print(f"Command result: {result}")
                break
                
        # 测试完成后断开连接
        for adapter_id, adapter in device_manager.adapters.items():
            await adapter.disconnect()
            print(f"Disconnected adapter: {adapter_id}")
                
    except Exception as e:
        print(f"Test error: {str(e)}")

# 运行异步测试
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_physical_devices())
