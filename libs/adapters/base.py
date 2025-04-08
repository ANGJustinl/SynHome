#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
设备适配器基类
为不同通信协议的物理设备提供统一接口
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger(__name__)

class DeviceAdapter(ABC):
    """设备适配器基类，用于与物理设备通信"""
    
    def __init__(self, adapter_id: str, config: Dict[str, Any]):
        """
        初始化适配器
        
        Args:
            adapter_id: 适配器唯一标识符
            config: 适配器配置
        """
        self.adapter_id = adapter_id
        self.config = config
        self.devices = {}  # 存储发现的设备
        self.status_callback = None  # 设备状态更新回调
        
    def register_status_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        注册设备状态更新回调函数
        
        Args:
            callback: 回调函数，参数为设备ID和状态数据
        """
        self.status_callback = callback
        
    def on_status_changed(self, device_id: str, status: Dict[str, Any]) -> None:
        """
        处理设备状态变更
        
        Args:
            device_id: 设备ID
            status: 设备状态数据
        """
        if self.status_callback:
            self.status_callback(device_id, status)
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        连接到协议服务器/网络
        
        Returns:
            是否连接成功
        """
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass
        
    @abstractmethod
    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        发现设备
        
        Returns:
            发现的设备列表
        """
        pass
        
    @abstractmethod
    async def send_command(self, device_id: str, command: Dict[str, Any]) -> bool:
        """
        发送命令到设备
        
        Args:
            device_id: 设备ID
            command: 命令数据
            
        Returns:
            命令是否成功发送
        """
        pass
