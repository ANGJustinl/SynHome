#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MQTT 设备适配器
用于通过 MQTT 协议连接和控制物理设备
"""

import asyncio
import json
import logging
import ssl
import time
from typing import Dict, List, Any, Optional, Callable

# 使用 asyncio-mqtt 库，它是 paho-mqtt 的异步包装器
import asyncio_mqtt as aiomqtt
from paho.mqtt import client as mqtt

from .base import DeviceAdapter

logger = logging.getLogger(__name__)

class MqttAdapter(DeviceAdapter):
    """MQTT 协议适配器，用于与支持 MQTT 的物理设备通信"""
    
    def __init__(self, adapter_id: str, config: Dict[str, Any]):
        """
        初始化 MQTT 适配器
        
        Args:
            adapter_id: 适配器唯一标识符
            config: 适配器配置信息
        """
        super().__init__(adapter_id, config)
        
        # MQTT 服务器配置
        mqtt_config = config.get("mqtt", {})
        self.broker_host = mqtt_config.get("host", "localhost")
        self.broker_port = mqtt_config.get("port", 1883)
        self.broker_keepalive = mqtt_config.get("keepalive", 60)
        self.use_ssl = mqtt_config.get("use_ssl", False)
        self.verify_ssl = mqtt_config.get("verify_ssl", True)
        
        # 认证信息
        self.username = mqtt_config.get("username")
        self.password = mqtt_config.get("password")
        
        # 客户端标识
        self.client_id = mqtt_config.get("client_id", f"synhome_mqtt_{adapter_id}_{int(time.time())}")
        
        # 主题配置
        topic_config = config.get("topics", {})
        self.topic_prefix = topic_config.get("prefix", "synhome/")
        self.command_topic_template = topic_config.get("command", "devices/{device_id}/command")
        self.status_topic_template = topic_config.get("status", "devices/{device_id}/status")
        self.discovery_topic = topic_config.get("discovery", "discovery")
        
        # 消息格式
        self.message_format = config.get("message_format", {})
        self.command_format = self.message_format.get("command", {
            "command": "{command}",
            "params": "{params}"
        })
        
        # 状态映射
        self.status_map = config.get("status_map", {})
        
        # MQTT 客户端
        self.client = None
        self.connected = False
        self.message_task = None
        self.subscriptions = set()  # 跟踪已订阅的主题
        
        # 重连配置
        self.reconnect_delay = config.get("reconnect_delay", 5)
        self.max_reconnect_attempts = config.get("max_reconnect_attempts", 10)
        self.auto_reconnect = config.get("auto_reconnect", True)
        self.reconnect_attempts = 0
        
    async def connect(self) -> bool:
        """
        连接到 MQTT 代理服务器
        
        Returns:
            连接是否成功
        """
        if self.connected and self.client:
            logger.info(f"Already connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            return True
            
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            
            # 配置 SSL 选项
            ssl_context = None
            if self.use_ssl:
                ssl_context = ssl.create_default_context()
                if not self.verify_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
            
            # 创建 MQTT 客户端
            self.client = aiomqtt.Client(
                hostname=self.broker_host,
                port=self.broker_port,
                username=self.username,
                password=self.password,
                client_id=self.client_id,
                tls_context=ssl_context if self.use_ssl else None,
                keepalive=self.broker_keepalive
            )
            
            # 连接到代理服务器
            await self.client.connect()
            self.connected = True
            self.reconnect_attempts = 0
            logger.info(f"Successfully connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            
            # 启动消息处理任务
            self.message_task = asyncio.create_task(self._process_messages())
            
            # 订阅设备状态主题
            status_topic = f"{self.topic_prefix}{self.status_topic_template.format(device_id='+')}"
            await self.client.subscribe(status_topic)
            self.subscriptions.add(status_topic)
            logger.info(f"Subscribed to status topic: {status_topic}")
            
            # 订阅发现主题
            discovery_topic = f"{self.topic_prefix}{self.discovery_topic}/response"
            await self.client.subscribe(discovery_topic)
            self.subscriptions.add(discovery_topic)
            logger.info(f"Subscribed to discovery topic: {discovery_topic}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {str(e)}")
            self.connected = False
            self.client = None
            return False
            
    async def disconnect(self) -> None:
        """断开与 MQTT 代理服务器的连接"""
        if self.message_task:
            self.message_task.cancel()
            try:
                await self.message_task
            except asyncio.CancelledError:
                pass
            self.message_task = None
            
        if self.client and self.connected:
            try:
                await self.client.disconnect()
                logger.info(f"Disconnected from MQTT broker at {self.broker_host}:{self.broker_port}")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT broker: {str(e)}")
            finally:
                self.client = None
                self.connected = False
                self.subscriptions.clear()
                
    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        发现设备 - 发送设备发现请求
        
        Returns:
            发现的设备列表
        """
        if not self.connected or not self.client:
            logger.error("Cannot discover devices: MQTT client not connected")
            return []
            
        try:
            # 创建队列来接收发现响应
            discovery_queue = asyncio.Queue()
            
            # 设置临时消息处理器
            async def on_discovery_message(message):
                try:
                    payload = json.loads(message.payload.decode())
                    await discovery_queue.put(payload)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in discovery response: {message.payload}")
            
            # 订阅发现响应主题
            discovery_topic = f"{self.topic_prefix}{self.discovery_topic}/response"
            async with self.client.filtered_messages(discovery_topic) as messages:
                await self.client.subscribe(discovery_topic)
                
                # 发送发现请求
                request_topic = f"{self.topic_prefix}{self.discovery_topic}/request"
                discovery_request = {
                    "adapter_id": self.adapter_id,
                    "timestamp": time.time()
                }
                
                await self.client.publish(
                    request_topic, 
                    payload=json.dumps(discovery_request).encode()
                )
                
                logger.info(f"Sent device discovery request to topic: {request_topic}")
                
                # 设置发现超时
                discovery_timeout = 10.0  # 10秒超时
                start_time = asyncio.get_event_loop().time()
                
                # 收集设备信息
                devices = []
                discovery_complete = False
                
                async for message in messages:
                    try:
                        payload = json.loads(message.payload.decode())
                        
                        # 检查是否为批量设备列表
                        if "devices" in payload:
                            batch_devices = payload["devices"]
                            devices.extend(batch_devices)
                            logger.info(f"Received batch of {len(batch_devices)} devices")
                            
                            # 检查是否是最后一批设备
                            if payload.get("complete", False):
                                discovery_complete = True
                                break
                        
                        # 单个设备
                        elif "device_id" in payload and "type" in payload:
                            devices.append(payload)
                            logger.info(f"Discovered device: {payload['device_id']}")
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in discovery message: {message.payload}")
                    
                    # 检查是否超时
                    if asyncio.get_event_loop().time() - start_time > discovery_timeout:
                        logger.warning("Discovery timed out")
                        break
            
            # 处理发现的设备
            for device in devices:
                device_id = device["device_id"]
                self.devices[device_id] = device
                
                # 订阅该设备的状态主题（如果还没有订阅）
                status_topic = f"{self.topic_prefix}{self.status_topic_template.format(device_id=device_id)}"
                if status_topic not in self.subscriptions:
                    await self.client.subscribe(status_topic)
                    self.subscriptions.add(status_topic)
            
            logger.info(f"Discovery completed. Found {len(devices)} devices")
            return devices
            
        except Exception as e:
            logger.error(f"Error discovering devices: {str(e)}")
            return []
            
    async def send_command(self, device_id: str, command: Dict[str, Any]) -> bool:
        """
        向设备发送命令
        
        Args:
            device_id: 设备ID
            command: 命令内容
            
        Returns:
            命令是否成功发送
        """
        if not self.connected or not self.client:
            logger.error(f"Cannot send command: MQTT client not connected")
            return False
            
        try:
            # 格式化命令主题
            command_topic = f"{self.topic_prefix}{self.command_topic_template.format(device_id=device_id)}"
            
            # 准备命令消息
            cmd = command.get("command", "")
            params = command.get("params", {}) or {}
            
            # 使用命令模板格式化消息
            cmd_template = self.command_format.copy()
            msg_text = json.dumps(cmd_template).replace('"{command}"', json.dumps(cmd))
            msg_text = msg_text.replace('"{params}"', json.dumps(params))
            
            # 解析成最终的JSON对象
            msg = json.loads(msg_text)
            
            # 发送命令
            await self.client.publish(
                command_topic,
                payload=json.dumps(msg).encode()
            )
            
            logger.info(f"Sent command to device {device_id} on topic {command_topic}: {cmd}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending command to device {device_id}: {str(e)}")
            
            # 如果是连接问题，尝试重连
            if isinstance(e, aiomqtt.MqttError) and self.auto_reconnect:
                asyncio.create_task(self._reconnect())
                
            return False

    async def _process_messages(self) -> None:
        """处理传入的 MQTT 消息"""
        try:
            # 订阅状态通配符主题
            status_topic_pattern = f"{self.topic_prefix}{self.status_topic_template.format(device_id='+')}"
            
            async with self.client.filtered_messages(status_topic_pattern) as messages:
                await self.client.subscribe(status_topic_pattern)
                self.subscriptions.add(status_topic_pattern)
                
                async for message in messages:
                    try:
                        # 从主题提取设备ID
                        topic_parts = message.topic.split('/')
                        if len(topic_parts) < 3:
                            logger.warning(f"Invalid status topic format: {message.topic}")
                            continue
                            
                        device_id = topic_parts[-2]  # 通常格式是 prefix/devices/{device_id}/status
                        
                        # 解析状态数据
                        try:
                            status_data = json.loads(message.payload.decode())
                            
                            # 应用状态映射
                            mapped_status = self._map_status(status_data)
                            
                            # 触发状态更新回调
                            self.on_status_changed(device_id, mapped_status)
                            
                            logger.debug(f"Received status update for device {device_id}: {mapped_status}")
                            
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in status message for device {device_id}: {message.payload}")
                            
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            logger.error(f"MQTT message processing error: {str(e)}")
            
            # 如果不是因为取消而退出，尝试重连
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect())
                
    async def _reconnect(self) -> None:
        """断线重连逻辑"""
        # 如果已经达到最大重连次数，则放弃
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Failed to reconnect after {self.reconnect_attempts} attempts")
            return
            
        # 增加重连计数并计算延迟（指数退避）
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 300)
        
        logger.info(f"Attempting to reconnect (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}) in {delay} seconds")
        
        # 等待延迟时间
        await asyncio.sleep(delay)
        
        # 尝试重新连接
        try:
            await self.disconnect()  # 确保断开任何现有连接
            success = await self.connect()
            
            if success:
                logger.info("Reconnected successfully")
                
                # 重新订阅之前的主题
                saved_subscriptions = list(self.subscriptions)
                for topic in saved_subscriptions:
                    try:
                        await self.client.subscribe(topic)
                        logger.info(f"Resubscribed to topic: {topic}")
                    except Exception as e:
                        logger.error(f"Failed to resubscribe to topic {topic}: {str(e)}")
            else:
                # 继续尝试重连
                asyncio.create_task(self._reconnect())
                
        except Exception as e:
            logger.error(f"Error during reconnect: {str(e)}")
            # 继续尝试重连
            asyncio.create_task(self._reconnect())
            
    def _map_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据定义的映射转换状态值
        
        Args:
            status: 原始状态数据
            
        Returns:
            映射后的状态数据
        """
        if not self.status_map:
            return status
            
        mapped_status = {}
        
        for key, value in status.items():
            # 检查这个状态值是否有映射
            if key in self.status_map:
                key_map = self.status_map[key]
                
                # 值映射
                if isinstance(key_map, dict) and "values" in key_map and value in key_map["values"]:
                    mapped_status[key] = key_map["values"][value]
                # 键映射
                elif isinstance(key_map, str):
                    mapped_status[key_map] = value
                else:
                    mapped_status[key] = value
            else:
                mapped_status[key] = value
                
        return mapped_status
