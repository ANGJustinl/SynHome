#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SynHome Device Mock Server
模拟各种家电设备的HTTP和WebSocket服务器
用于测试设备管理器和通信协议
"""

import asyncio
import json
import logging
import random
import time
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 设备状态存储
device_states: Dict[str, Dict] = {}
websocket_connections: List[WebSocket] = []

@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    name: str
    device_type: str
    capabilities: List[str]
    current_state: Dict[str, Any]
    last_updated: str
    online: bool = True

class DeviceCommand(BaseModel):
    """设备命令模型"""
    device_id: str
    capability: str
    value: Any
    timestamp: Optional[str] = None

class DeviceResponse(BaseModel):
    """设备响应模型"""
    success: bool
    device_id: str
    capability: str
    previous_value: Any
    new_value: Any
    timestamp: str
    message: str = ""

# 模拟设备数据
DEVICE_TEMPLATES = {
    "thermostat": {
        "name": "智能空调",
        "capabilities": ["power", "temperature", "mode"],
        "initial_state": {
            "power": "off",
            "temperature": 24,
            "mode": "auto"
        }
    },
    "light": {
        "name": "智能灯光",
        "capabilities": ["power", "brightness", "color"],
        "initial_state": {
            "power": "off",
            "brightness": 0,
            "color": "white"
        }
    },
    "rice_cooker": {
        "name": "智能电饭煲",
        "capabilities": ["power", "program", "timer"],
        "initial_state": {
            "power": "off",
            "program": "标准煮",
            "timer": 0
        }
    },
    "washing_machine": {
        "name": "智能洗衣机",
        "capabilities": ["power", "program", "water_level", "spin_speed"],
        "initial_state": {
            "power": "off",
            "program": "标准洗",
            "water_level": "中等",
            "spin_speed": 800
        }
    }
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化设备
    logger.info("🚀 正在启动SynHome设备模拟服务器...")
    initialize_devices()

    # 启动设备状态更新任务
    update_task = asyncio.create_task(device_status_updater())

    yield

    # 关闭时清理
    update_task.cancel()
    logger.info("🛑 SynHome设备模拟服务器已关闭")

app = FastAPI(
    title="SynHome Device Mock Server",
    description="模拟家电设备的测试后端，支持HTTP REST API和WebSocket",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def initialize_devices():
    """初始化模拟设备"""
    global device_states

    for device_type, template in DEVICE_TEMPLATES.items():
        for i in range(1, 3):  # 每种类型创建2个设备
            device_id = f"{device_type}_{i:03d}"
            device_info = DeviceInfo(
                device_id=device_id,
                name=f"{template['name']} {i}",
                device_type=device_type,
                capabilities=template["capabilities"],
                current_state=template["initial_state"].copy(),
                last_updated=datetime.now().isoformat(),
                online=True
            )
            device_states[device_id] = asdict(device_info)

    logger.info(f"✅ 已初始化 {len(device_states)} 个模拟设备")

async def device_status_updater():
    """定期更新设备状态（模拟真实设备的状态变化）"""
    while True:
        try:
            for device_id, device in device_states.items():
                if device["online"] and device["current_state"].get("power") == "on":
                    # 模拟运行中的设备状态变化
                    if device["device_type"] == "thermostat":
                        # 模拟温度变化
                        current_temp = device["current_state"]["temperature"]
                        target_temp = current_temp + random.uniform(-0.5, 0.5)
                        device["current_state"]["temperature"] = round(target_temp, 1)

                    elif device["device_type"] == "light":
                        # 模拟亮度微调
                        current_brightness = device["current_state"]["brightness"]
                        if current_brightness > 0:
                            device["current_state"]["brightness"] = max(
                                0, current_brightness + random.randint(-2, 2)
                            )

                    device["last_updated"] = datetime.now().isoformat()

            # 通过WebSocket广播状态更新
            if websocket_connections:
                await broadcast_device_states()

        except Exception as e:
            logger.error(f"设备状态更新错误: {e}")

        await asyncio.sleep(10)  # 每10秒更新一次

async def broadcast_device_states():
    """通过WebSocket广播所有设备状态"""
    if not websocket_connections:
        return

    message = {
        "type": "device_states_update",
        "timestamp": datetime.now().isoformat(),
        "devices": list(device_states.values())
    }

    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"WebSocket广播失败: {e}")
            disconnected.append(ws)

    # 清理断开的连接
    for ws in disconnected:
        websocket_connections.remove(ws)

# HTTP API 端点
@app.get("/", response_class=HTMLResponse)
async def root():
    """返回测试页面"""
    return """
    <html>
        <head><title>SynHome Device Mock Server</title></head>
        <body>
            <h1>🏠 SynHome 设备模拟服务器</h1>
            <p>API文档: <a href="/docs">/docs</a></p>
            <p>WebSocket测试: <a href="/ws-test">/ws-test</a></p>
            <h2>设备列表:</h2>
            <ul>
                <li><a href="/devices">GET /devices</a> - 获取所有设备</li>
                <li><a href="/devices/{device_id}">GET /devices/{device_id}</a> - 获取单个设备</li>
                <li>POST /devices/{device_id}/command - 发送设备命令</li>
            </ul>
        </body>
    </html>
    """

@app.get("/devices")
async def get_all_devices():
    """获取所有设备状态"""
    return {
        "devices": list(device_states.values()),
        "count": len(device_states),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/devices/{device_id}")
async def get_device(device_id: str):
    """获取单个设备状态"""
    if device_id not in device_states:
        raise HTTPException(status_code=404, detail="设备未找到")

    return device_states[device_id]

@app.post("/devices/{device_id}/command")
async def send_device_command(device_id: str, command: DeviceCommand):
    """向设备发送命令"""
    if device_id not in device_states:
        raise HTTPException(status_code=404, detail="设备未找到")

    device = device_states[device_id]

    if not device["online"]:
        raise HTTPException(status_code=503, detail="设备离线")

    # 验证能力是否存在
    if command.capability not in device["capabilities"]:
        raise HTTPException(status_code=400, detail=f"设备不支持{command.capability}能力")

    # 记录之前的值
    previous_value = device["current_state"].get(command.capability)

    try:
        # 模拟命令执行延迟
        await asyncio.sleep(0.1)

        # 更新设备状态
        device["current_state"][command.capability] = command.value
        device["last_updated"] = datetime.now().isoformat()

        # 模拟连锁反应
        await simulate_device_side_effects(device_id, command.capability, command.value)

        # 通过WebSocket广播状态变化
        if websocket_connections:
            await broadcast_device_change(device_id, command.capability, previous_value, command.value)

        return DeviceResponse(
            success=True,
            device_id=device_id,
            capability=command.capability,
            previous_value=previous_value,
            new_value=command.value,
            timestamp=datetime.now().isoformat(),
            message=f"成功设置{command.capability}为{command.value}"
        )

    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        return DeviceResponse(
            success=False,
            device_id=device_id,
            capability=command.capability,
            previous_value=previous_value,
            new_value=previous_value,
            timestamp=datetime.now().isoformat(),
            message=f"命令执行失败: {str(e)}"
        )

async def simulate_device_side_effects(device_id: str, capability: str, value: Any):
    """模拟设备副作用"""
    device = device_states[device_id]

    if capability == "power" and value == "off":
        # 关闭电源时重置其他能力
        if device["device_type"] == "light":
            device["current_state"]["brightness"] = 0
        elif device["device_type"] == "thermostat":
            device["current_state"]["temperature"] = 24
            device["current_state"]["mode"] = "auto"
        elif device["device_type"] == "rice_cooker":
            device["current_state"]["program"] = "标准煮"
            device["current_state"]["timer"] = 0
        elif device["device_type"] == "washing_machine":
            device["current_state"]["program"] = "标准洗"
            device["current_state"]["water_level"] = "中等"
            device["current_state"]["spin_speed"] = 800

    elif capability == "power" and value == "on":
        # 开启电源时的默认设置
        if device["device_type"] == "light":
            device["current_state"]["brightness"] = 80
        elif device["device_type"] == "thermostat":
            device["current_state"]["temperature"] = 24

async def broadcast_device_change(device_id: str, capability: str, old_value: Any, new_value: Any):
    """通过WebSocket广播单个设备状态变化"""
    message = {
        "type": "device_state_change",
        "timestamp": datetime.now().isoformat(),
        "device_id": device_id,
        "capability": capability,
        "previous_value": old_value,
        "new_value": new_value
    }

    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"WebSocket广播失败: {e}")
            disconnected.append(ws)

    for ws in disconnected:
        websocket_connections.remove(ws)

# WebSocket 端点
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接用于实时设备状态更新"""
    await websocket.accept()
    websocket_connections.append(websocket)

    logger.info(f"📡 新的WebSocket连接: {id(websocket)} (当前连接数: {len(websocket_connections)})")

    try:
        # 发送当前所有设备状态
        await websocket.send_text(json.dumps({
            "type": "initial_state",
            "timestamp": datetime.now().isoformat(),
            "devices": list(device_states.values())
        }, ensure_ascii=False))

        # 保持连接并处理客户端消息
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }))
            elif message.get("type") == "get_device":
                device_id = message.get("device_id")
                if device_id in device_states:
                    await websocket.send_text(json.dumps({
                        "type": "device_state",
                        "device_id": device_id,
                        "state": device_states[device_id],
                        "timestamp": datetime.now().isoformat()
                    }, ensure_ascii=False))

    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info(f"📡 WebSocket连接断开: {id(websocket)} (当前连接数: {len(websocket_connections)})")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

@app.get("/ws-test", response_class=HTMLResponse)
async def websocket_test_page():
    """WebSocket测试页面"""
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>SynHome WebSocket Test</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .messages {
                    border: 1px solid #ccc;
                    height: 400px;
                    overflow-y: scroll;
                    padding: 10px;
                    margin: 10px 0;
                    background-color: #f9f9f9;
                }
                .message { margin: 5px 0; padding: 5px; }
                .system { background-color: #e3f2fd; }
                .device { background-color: #fff3e0; }
                button { padding: 10px; margin: 5px; }
            </style>
        </head>
        <body>
            <h1>🔌 SynHome WebSocket 测试</h1>
            <div>
                <button onclick="connect()">连接WebSocket</button>
                <button onclick="disconnect()">断开连接</button>
                <button onclick="clearMessages()">清空消息</button>
            </div>
            <div id="status" style="margin: 10px 0; font-weight: bold;">状态: 未连接</div>
            <div id="messages" class="messages"></div>

            <script>
                let ws = null;
                const messages = document.getElementById('messages');
                const status = document.getElementById('status');

                function addMessage(message, type = 'system') {
                    const div = document.createElement('div');
                    div.className = `message ${type}`;
                    div.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong>: ${JSON.stringify(message, null, 2)}`;
                    messages.appendChild(div);
                    messages.scrollTop = messages.scrollHeight;
                }

                function connect() {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        addMessage('已经连接', 'system');
                        return;
                    }

                    ws = new WebSocket('ws://localhost:8000/ws');

                    ws.onopen = function(event) {
                        status.textContent = '状态: 已连接';
                        status.style.color = 'green';
                        addMessage('WebSocket连接已建立', 'system');
                    };

                    ws.onmessage = function(event) {
                        const data = JSON.parse(event.data);
                        addMessage(data, 'device');
                    };

                    ws.onclose = function(event) {
                        status.textContent = '状态: 未连接';
                        status.style.color = 'red';
                        addMessage('WebSocket连接已关闭', 'system');
                    };

                    ws.onerror = function(error) {
                        addMessage('WebSocket错误: ' + error, 'system');
                    };
                }

                function disconnect() {
                    if (ws) {
                        ws.close();
                        ws = null;
                    }
                }

                function clearMessages() {
                    messages.innerHTML = '';
                }

                // 定期ping
                setInterval(() => {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({type: 'ping'}));
                    }
                }, 30000);
            </script>
        </body>
    </html>
    """

@app.post("/simulation/reset")
async def reset_simulation():
    """重置所有设备到初始状态"""
    global device_states
    initialize_devices()
    return {"message": "模拟器已重置", "timestamp": datetime.now().isoformat()}

@app.post("/simulation/offline/{device_id}")
async def set_device_offline(device_id: str):
    """设置设备离线"""
    if device_id not in device_states:
        raise HTTPException(status_code=404, detail="设备未找到")

    device_states[device_id]["online"] = False
    device_states[device_id]["last_updated"] = datetime.now().isoformat()

    return {"message": f"设备{device_id}已设置为离线"}

@app.post("/simulation/online/{device_id}")
async def set_device_online(device_id: str):
    """设置设备在线"""
    if device_id not in device_states:
        raise HTTPException(status_code=404, detail="设备未找到")

    device_states[device_id]["online"] = True
    device_states[device_id]["last_updated"] = datetime.now().isoformat()

    return {"message": f"设备{device_id}已设置为在线"}

def main():
    """主函数，支持命令行参数"""
    parser = argparse.ArgumentParser(description="SynHome设备模拟服务器")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口 (默认: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务器主机 (默认: 0.0.0.0)")
    parser.add_argument("--reload", action="store_true", help="启用自动重载 (开发模式)")
    parser.add_argument("--log-level", type=str, default="info",
                       choices=["debug", "info", "warning", "error", "critical"],
                       help="日志级别 (默认: info)")

    args = parser.parse_args()

    print(f"🏠 启动SynHome设备模拟服务器...")
    print(f"📖 API文档: http://{args.host}:{args.port}/docs")
    print(f"🔌 WebSocket测试: http://{args.host}:{args.port}/ws-test")

    uvicorn.run(
        "device_mock_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )

if __name__ == "__main__":
    main()