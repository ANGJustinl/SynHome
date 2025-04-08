#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
设备协议适配器模块
为不同协议的设备提供统一的接口
"""

from .base import DeviceAdapter
from .websocket_adapter import WebSocketAdapter
from .mqtt_adapter import MqttAdapter

# 适配器类型映射，用于根据配置创建适配器实例
ADAPTER_TYPES = {
    "websocket": WebSocketAdapter,
    "mqtt": MqttAdapter
}

def get_adapter_class(adapter_type: str) -> type:
    """
    获取适配器类
    
    Args:
        adapter_type: 适配器类型名称
        
    Returns:
        适配器类
    """
    return ADAPTER_TYPES.get(adapter_type)
