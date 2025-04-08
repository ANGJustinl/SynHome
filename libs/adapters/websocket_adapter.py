#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WebSocket 设备适配器
用于通过 WebSocket 协议连接和控制物理设备
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Callable
import ssl
import time
import websockets
from urllib.parse import urlparse

from .base import DeviceAdapter

logger = logging.getLogger(__name__)

class WebSocketAdapter(DeviceAdapter):
    """WebSocket 协议适配器，用于与支持 WebSocket 的物理设备通信"""
    
    def __init__(self, adapter_id: str, config: Dict[str, Any]):
        """
        初始化 WebSocket 适配器
        
        Args:
            adapter_id: 适配器唯一标识符
            config: 适配器配置信息
        """
        super().__init__(adapter_id, config)
        
        # WebSocket 连接配置
        self.url = config.get("url", "ws://localhost:8080")
        self.use_ssl = config.get("use_ssl", False)
        self.verify_ssl = config.get("verify_ssl", True)
        self.timeout = config.get("timeout", 10)
        self.reconnect_delay = config.get("reconnect_delay", 5)
        self.max_reconnect_attempts = config.get("max_reconnect_attempts", 10)
        self.ping_interval = config.get("ping_interval", 30)
        self.auto_reconnect = config.get("auto_reconnect", True)
        
        # 认证信息
        self.auth = config.get("auth", {})
        self.auth_type = self.auth.get("type", "none")  # none, token, basic, api_key
        
        # 消息格式配置
        self.message_format = config.get("message_format", {})
        self.command_template = self.message_format.get("command_template", {
            "type": "command",
            "device_id": "{device_id}",
            "command": "{command}",
            "params": "{params}"
        })
        self.status_message_type = self.message_format.get("status_message_type", "status")
        
        # 设备状态映射
        self.status_map = config.get("status_map", {})
        
        # WebSocket 对象
        self.ws = None
        self.connected = False
        self.connection_task = None
        self.listen_task = None
        self.ping_task = None
        self.reconnect_attempts = 0
        
    async def connect(self) -> bool:
        """
        连接到 WebSocket 服务器
        
        Returns:
            连接是否成功
        """
        if self.connected and self.ws:
            logger.info(f"Already connected to WebSocket at {self.url}")
            return True
            
        try:
            logger.info(f"Connecting to WebSocket at {self.url}")
            
            # 准备 SSL 上下文（如果需要）
            ssl_context = None
            if self.use_ssl:
                ssl_context = ssl.create_default_context()
                if not self.verify_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
            
            # 准备连接选项
            extra_options = {}
            if self.auth_type == "token":
                # 如果使用令牌认证，添加到头部
                headers = {"Authorization": f"Bearer {self.auth.get('token', '')}"}
                extra_options["extra_headers"] = headers
            
            # 创建 WebSocket 连接
            self.ws = await websockets.connect(
                self.url,
                ssl=ssl_context,
                ping_interval=self.ping_interval,
                ping_timeout=self.timeout,
                close_timeout=self.timeout,
                **extra_options
            )
            
            # 认证处理（如果需要）
            if self.auth_type == "basic" or self.auth_type == "api_key":
                auth_data = {
                    "type": "auth"
                }
                
                if self.auth_type == "basic":
                    auth_data.update({
                        "username": self.auth.get("username", ""),
                        "password": self.auth.get("password", "")
                    })
                elif self.auth_type == "api_key":
                    auth_data.update({
                        "api_key": self.auth.get("api_key", "")
                    })
                    
                await self.ws.send(json.dumps(auth_data))
                
                # 等待认证响应
                try:
                    response = await asyncio.wait_for(self.ws.recv(), self.timeout)
                    response_data = json.loads(response)
                    
                    if not response_data.get("success", False):
                        logger.error(f"Authentication failed: {response_data.get('message', 'Unknown error')}")
                        await self.ws.close()
                        self.ws = None
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("Authentication timed out")
                    await self.ws.close()
                    self.ws = None
                    return False
            
            self.connected = True
            self.reconnect_attempts = 0
            logger.info(f"Successfully connected to WebSocket at {self.url}")
            
            # 启动消息监听任务
            self.listen_task = asyncio.create_task(self._listen_messages())
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {str(e)}")
            self.connected = False
            self.ws = None
            return False
            
    async def disconnect(self) -> None:
        """断开与 WebSocket 服务器的连接"""
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
            self.listen_task = None
            
        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
            self.ping_task = None
            
        if self.ws:
            try:
                await self.ws.close()
                logger.info(f"Disconnected from WebSocket at {self.url}")
            except Exception as e:
                logger.error(f"Error disconnecting from WebSocket: {str(e)}")
            finally:
                self.ws = None
                self.connected = False
            
    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        发现设备 - 发送设备发现请求
        
        Returns:
            发现的设备列表
        """
        if not self.connected or not self.ws:
            logger.error("Cannot discover devices: WebSocket not connected")
            return []
            
        try:
            # 发送设备发现消息
            discovery_message = {
                "type": "discovery",
                "adapter_id": self.adapter_id
            }
            
            await self.ws.send(json.dumps(discovery_message))
            
            # 等待设备列表响应
            # 创建一个队列来存储发现的设备
            discovery_queue = asyncio.Queue()
            
            # 设置接收超时
            discovery_timeout = self.timeout
            start_time = asyncio.get_event_loop().time()
            
            # 启动临时监听任务来接收设备列表
            async def discovery_listener():
                try:
                    while True:
                        # 检查超时
                        if asyncio.get_event_loop().time() - start_time > discovery_timeout:
                            break
                            
                        # 等待响应
                        try:
                            response = await asyncio.wait_for(self.ws.recv(), 1.0)
                            data = json.loads(response)
                            
                            # 判断是否为设备发现响应
                            if data.get("type") == "discovery_response":
                                devices = data.get("devices", [])
                                for device in devices:
                                    await discovery_queue.put(device)
                                    
                                # 如果响应中明确表示设备列表已完成，则退出
                                if data.get("complete", False):
                                    break
                        except asyncio.TimeoutError:
                            # 短暂超时，继续等待
                            continue
                            
                except Exception as e:
                    logger.error(f"Error in discovery listener: {str(e)}")
                finally:
                    # 标记队列结束
                    await discovery_queue.put(None)
                    
            # 启动临时监听任务
            listener_task = asyncio.create_task(discovery_listener())
            
            # 从队列中收集设备
            devices = []
            while True:
                device = await discovery_queue.get()
                if device is None:  # 结束标记
                    break
                devices.append(device)
            
            # 确保监听任务结束
            await listener_task
            
            # 处理发现的设备
            for device in devices:
                self.devices[device["device_id"]] = device
                
            logger.info(f"Discovered {len(devices)} devices via WebSocket")
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
        if not self.connected or not self.ws:
            logger.error(f"Cannot send command: WebSocket not connected")
            return False
            
        try:
            # 准备命令消息
            cmd = command.get("command", "")
            params = command.get("params", {})
            
            # 使用命令模板格式化消息
            cmd_template = self.command_template.copy()
            msg = json.dumps(cmd_template).replace('"{device_id}"', json.dumps(device_id))
            msg = msg.replace('"{command}"', json.dumps(cmd))
            msg = msg.replace('"{params}"', json.dumps(params))
            
            # 发送命令
            await self.ws.send(msg)
            logger.debug(f"Sent command to device {device_id}: {cmd} with params {params}")
            
            # 对于某些命令，可能需要等待确认响应
            # 这取决于设备的特定实现，此处暂不实现
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending command to device {device_id}: {str(e)}")
            
            # 尝试重连
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect())
                
            return False
            
    async def _listen_messages(self) -> None:
        """监听并处理 WebSocket 消息"""
        try:
            while self.connected and self.ws:
                try:
                    # 接收消息
                    message = await self.ws.recv()
                    
                    # 解析消息
                    try:
                        data = json.loads(message)
                        message_type = data.get("type", "")
                        
                        # 处理状态更新消息
                        if message_type == self.status_message_type:
                            device_id = data.get("device_id")
                            status = data.get("status", {})
                            
                            if device_id and status:
                                # 映射状态值
                                mapped_status = self._map_status(status)
                                
                                # 调用状态更新回调
                                if mapped_status:
                                    self.on_status_changed(device_id, mapped_status)
                        
                        # 处理设备事件（如果有）
                        elif message_type == "event":
                            # 可以在这里处理设备事件
                            # 暂不实现
                            pass
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON message: {message}")
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    break
                    
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            logger.error(f"Error in WebSocket message listener: {str(e)}")
        finally:
            self.connected = False
            
            # 如果需要自动重连
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect())
            
    async def _reconnect(self) -> None:
        """断线重连逻辑"""
        # 如果已经达到最大重连次数，则放弃
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Failed to reconnect after {self.reconnect_attempts} attempts")
            return
            
        # 增加重连计数并计算延迟
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
                
                # 刷新设备列表
                await self.discover_devices()
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
