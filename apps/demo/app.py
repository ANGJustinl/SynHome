#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FastAPI backend for device control demo
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder

from libs.utils.config import ConfigLoader
from libs.devices.device_manager import DeviceManager
from apps.demo.debug_middleware import DebugMiddleware

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Smart Home Device Control Demo")

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(DebugMiddleware)

# Load configuration
try:
    config = ConfigLoader("config/demo.yaml").load()
    api_key = config["zhipuai"]["api_key"]
except Exception as e:
    logger.error(f"Error loading config: {str(e)}")
    api_key = os.getenv("ZHIPUAI_API_KEY", "")

# Create device manager and load devices
device_manager = DeviceManager()

# Load devices from configuration
try:
    device_manager.load_devices_from_config(config["devices"])
    if api_key:
        device_manager.enable_llm_control(api_key)
    logger.info(f"Loaded {len(device_manager.get_all_devices())} devices")
except Exception as e:
    logger.error(f"Error loading devices: {str(e)}")

class CommandRequest(BaseModel):
    command: str
    device_id: Optional[str] = None

# Set up static files
static_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

@app.get("/")
async def root():
    """Serve the main page"""
    logger.info("Serving index page")
    return FileResponse(static_dir / "index.html")

@app.get("/devices")
async def list_devices():
    """Get list of all devices"""
    try:
        device_list = []
        for device in device_manager.get_all_devices():
            device_data = {
                "id": device.id,
                "name": device.name,
                "type": device.type,
                "state": device.state.value,
                "capabilities": device.get_capability_info()
            }
            device_list.append(device_data)
            
        logger.info(f"Returning {len(device_list)} devices")
        return JSONResponse(
            content=jsonable_encoder(device_list),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"Error listing devices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/devices/{device_id}/command")
async def send_command_to_device(device_id: str, command: CommandRequest):
    """Send command to specific device"""
    try:
        logger.info(f"Received command for device {device_id}: {command.command}")
        
        device = device_manager.get_device_by_id(device_id)
        if not device:
            logger.warning(f"Device not found: {device_id}")
            raise HTTPException(status_code=404, detail="Device not found")
            
        if not device.process_natural_command(command.command):
            logger.warning("Command processing failed")
            raise HTTPException(status_code=400, detail="Command processing failed")
        
        return JSONResponse(
            content=jsonable_encoder({
                "success": True,
                "message": "Command executed successfully",
                "state": device.state.value,
                "capabilities": device.get_capability_info()
            }),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/command")
async def process_global_command(command: CommandRequest):
    """Process a command without specifying device"""
    try:
        logger.info(f"Received global command: {command.command}")
        
        result = device_manager.process_command(command.command, command.device_id)
        if not result["success"]:
            logger.warning(f"Command processing failed: {result['message']}")
            raise HTTPException(status_code=400, detail=result["message"])
        
        # 区分处理不同类型的命令结果
        if "sub_commands" in result:  # 跨设备多操作命令
            return JSONResponse(
                content=jsonable_encoder({
                    "success": True,
                    "message": result["message"],
                    "device_count": result["device_count"],
                    "success_count": result["success_count"],
                    "sub_commands": result["sub_commands"]
                }),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Cache-Control": "no-cache"
                }
            )
        elif "device_count" in result:  # 多设备命令（同类型）
            return JSONResponse(
                content=jsonable_encoder({
                    "success": True,
                    "message": result["message"],
                    "device_count": result["device_count"],
                    "success_count": result["success_count"]
                }),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Cache-Control": "no-cache"
                }
            )
        else:  # 单设备命令
            return JSONResponse(
                content=jsonable_encoder({
                    "success": True,
                    "message": f"Command executed successfully on {result['device_name']}",
                    "device_id": result["device_id"]
                }),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Cache-Control": "no-cache"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/device-info")
async def get_device_info():
    """获取设备配置信息"""
    try:
        # 从配置文件中获取设备配置
        device_configs = config.get("devices", [])
        
        # 提取UI需要的配置信息
        device_types = set()
        capabilities = {}
        
        for device_config in device_configs:
            # 收集设备类型
            device_type = device_config.get("type")
            if device_type:
                device_types.add(device_type)
            
            # 收集能力信息
            for cap_dict in device_config.get("capabilities", []):
                for cap_name, cap_config in cap_dict.items():
                    if cap_name not in capabilities:
                        capabilities[cap_name] = {
                            "type": cap_config.get("type"),
                            "values": cap_config.get("values") if cap_config.get("type") == "enum" else None,
                            "unit": cap_config.get("unit") if cap_config.get("type") == "number" else None
                        }
        
        return JSONResponse(
            content=jsonable_encoder({
                "device_types": list(device_types),
                "capabilities": capabilities
            }),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"Error getting device info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    try:
        # 加载和初始化所有适配器
        if "adapters" in config:
            await device_manager.load_adapters_from_config(config["adapters"])
            logger.info(f"Initialized {len(device_manager.adapters)} device adapters")
            
            # 将物理设备与虚拟设备关联
            if "physical_devices" in config:
                await device_manager.associate_physical_devices(config["physical_devices"])
                logger.info("Associated physical devices with virtual models")
    except Exception as e:
        logger.error(f"Error initializing adapters: {str(e)}", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    try:
        # 断开所有适配器连接
        if hasattr(device_manager, "adapters"):
            for adapter_id, adapter in device_manager.adapters.items():
                logger.info(f"Disconnecting adapter: {adapter_id}")
                await adapter.disconnect()
            logger.info("All adapters disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting adapters: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")