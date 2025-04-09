#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MQTT 设备适配器 - 基于paho-mqtt的简化版
用于通过 MQTT 协议连接和控制物理设备
"""

import json
import logging
import time
from typing import Dict, List, Any

# 使用原生paho-mqtt而非asyncio包装器，简化实现
import paho.mqtt.client as mqtt

from .base import DeviceAdapter

logger = logging.getLogger(__name__)

class MqttAdapter(DeviceAdapter):
    """简化版 MQTT 协议适配器，用于与支持 MQTT 的物理设备通信"""
    
    def __init__(self, adapter_id: str, config: Dict[str, Any]):
        """初始化 MQTT 适配器"""
        super().__init__(adapter_id, config)
        
        # 提取 MQTT 配置
        mqtt_config = config.get("mqtt", {})
        self.host = mqtt_config.get("host", "localhost")
        self.port = mqtt_config.get("port", 1883)
        self.username = mqtt_config.get("username")
        self.password = mqtt_config.get("password")
        self.client_id = mqtt_config.get("client_id", f"synhome_{adapter_id}_{int(time.time())}")
        
        # 主题配置
        topics = config.get("topics", {})
        self.prefix = topics.get("prefix", "synhome/")
        self.cmd_topic = topics.get("command", "devices/{device_id}/cmd")
        self.state_topic = topics.get("status", "devices/{device_id}/state")
        
        # MQTT 客户端
        self.client = None
        self.connected = False
        
        # 状态映射
        self.status_map = config.get("status_map", {})
        
    async def connect(self) -> bool:
        """连接到 MQTT 代理服务器"""
        if self.connected and self.client:
            return True
            
        try:
            logger.info(f"连接到 MQTT 服务器: {self.host}:{self.port}")
            
            # 创建MQTT客户端
            self.client = mqtt.Client(client_id=self.client_id)
            
            # 设置回调函数
            self.client.on_message = self._on_message
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            # 设置认证信息(如果有)
            if self.username:
                self.client.username_pw_set(self.username, self.password)
            
            # 连接到MQTT代理
            self.client.connect(self.host, self.port)
            
            # 启动守护线程监听消息
            self.client.loop_start()
            
            self.connected = True
            logger.info("已连接到 MQTT 服务器")
            return True
            
        except Exception as e:
            logger.error(f"MQTT 连接失败: {str(e)}")
            self.client = None
            self.connected = False
            return False
            
    async def disconnect(self) -> None:
        """断开 MQTT 连接"""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("已断开 MQTT 连接")
            except Exception as e:
                logger.error(f"断开 MQTT 连接出错: {str(e)}")
            finally:
                self.client = None
                self.connected = False
                
    async def discover_devices(self) -> List[Dict[str, Any]]:
        """简化的设备发现实现 - 返回空列表，依赖配置中定义的物理设备"""
        return []
            
    async def send_command(self, device_id: str, command: Dict[str, Any]) -> bool:
        """向设备发送命令"""
        if not self.connected or not self.client:
            logger.error("MQTT 未连接，无法发送命令")
            return False
            
        try:
            # 构建命令主题
            topic = f"{self.prefix}{self.cmd_topic.format(device_id=device_id)}"
            
            # 发送命令
            result = self.client.publish(
                topic,
                payload=json.dumps(command)
            )
            
            # 检查发送结果
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"命令已发送到设备 {device_id}: {command}")
                return True
            else:
                logger.error(f"发送命令失败，错误代码: {result.rc}")
                return False
            
        except Exception as e:
            logger.error(f"发送命令出错: {str(e)}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """连接成功回调"""
        if rc == 0:
            logger.info("MQTT连接成功建立")
            # 订阅状态主题(使用通配符)
            topic = f"{self.prefix}{self.state_topic.format(device_id='+')}"
            client.subscribe(topic)
            logger.info(f"已订阅主题: {topic}")
        else:
            logger.error(f"MQTT连接失败，错误代码: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调"""
        logger.info(f"MQTT连接已断开，错误代码: {rc}")
        self.connected = False
    
    def _on_message(self, client, userdata, message):
        """接收消息回调"""
        try:
            # 从主题中提取设备ID
            topic = message.topic
            
            # 简单地假设主题格式为 prefix/devices/deviceId/state
            parts = topic.split('/')
            
            # 尝试找到设备ID
            device_id = None
            for i, part in enumerate(parts):
                if i < len(parts) - 1 and parts[i + 1] in ["state", "status"]:
                    device_id = part
                    break
            
            if not device_id:
                logger.warning(f"无法从主题中提取设备ID: {topic}")
                return
                
            # 解析状态数据
            payload = message.payload.decode()
            status = json.loads(payload)
            
            # 应用状态映射
            mapped_status = self._map_status(status)
            
            # 调用状态更新回调
            self.on_status_changed(device_id, mapped_status)
            logger.debug(f"收到设备 {device_id} 的状态更新")
            
        except json.JSONDecodeError:
            logger.warning(f"无效的JSON格式: {message.payload}")
        except Exception as e:
            logger.error(f"处理消息出错: {str(e)}")
            
    def _map_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """应用状态映射"""
        if not self.status_map:
            return status
            
        result = {}
        for key, value in status.items():
            # 查找键映射
            mapped_key = self.status_map.get(key, key)
            
            # 如果是字符串，直接使用映射后的键
            if isinstance(mapped_key, str):
                result[mapped_key] = value
            # 如果是字典，可能包含值映射
            elif isinstance(mapped_key, dict) and "values" in mapped_key:
                # 尝试映射值
                if value in mapped_key["values"]:
                    result[key] = mapped_key["values"][value]
                else:
                    result[key] = value
            else:
                # 使用原始键值
                result[key] = value
                
        return result