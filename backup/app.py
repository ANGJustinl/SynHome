#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FastAPI backend for device control demo with enhanced configuration validation
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder

# Import new configuration system
from libs.config import load_config, AppSettings
from libs.config.startup import validate_startup_config
from libs.config.validation_service import get_validation_service
from libs.logging import setup_logging, get_logger
from libs.devices.device_manager import DeviceManager
from apps.demo.debug_middleware import DebugMiddleware

# Global variables for configuration and services
app_settings: Optional[AppSettings] = None
device_manager: Optional[DeviceManager] = None
logger = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with proper configuration validation and initialization"""
    global app_settings, device_manager, logger

    logger = get_logger("startup")

    try:
        # Step 1: Validate and load configuration
        logger.info("Starting SynHome application with configuration validation...")

        # Determine config file path
        config_file = os.getenv("SYNHOME_CONFIG_FILE", "config/demo.yaml")

        # Perform startup validation
        startup_result = validate_startup_config(
            config_file=config_file,
            strict_mode=os.getenv("SYNHOME_STRICT_VALIDATION", "false").lower() == "true",
            auto_migrate=os.getenv("SYNHOME_AUTO_MIGRATE", "true").lower() == "true"
        )

        if not startup_result.success:
            logger.error("Configuration validation failed during startup")
            logger.error(f"Critical errors: {startup_result.critical_failures}")
            logger.error(f"Recommendations: {startup_result.recommendations}")

            # In development mode, we might want to continue with warnings
            if startup_result.app_settings and startup_result.app_settings.environment.value == "development":
                logger.warning("Continuing in development mode despite configuration issues")
                app_settings = startup_result.app_settings
            else:
                logger.error("Cannot start application due to critical configuration errors")
                raise RuntimeError(f"Configuration validation failed: {'; '.join(startup_result.critical_failures)}")
        else:
            app_settings = startup_result.app_settings
            logger.info("Configuration validation completed successfully")

            # Log any warnings
            if startup_result.warnings:
                for warning in startup_result.warnings:
                    logger.warning(f"Configuration warning: {warning}")

            # Log recommendations
            if startup_result.recommendations:
                logger.info("Configuration recommendations:")
                for rec in startup_result.recommendations:
                    logger.info(f"  - {rec}")

        # Step 2: Setup logging with validated configuration
        logger.info("Setting up logging system...")
        setup_logging(app_settings.logging)
        logger = get_logger("synhome_app")
        logger.info("Logging system initialized")

        # Step 3: Initialize device manager
        logger.info("Initializing device manager...")
        device_manager = DeviceManager()

        # Step 4: Load devices from configuration
        logger.info("Loading devices from configuration...")
        try:
            # Convert new device config format to legacy format for device manager
            devices_config = []
            if hasattr(app_settings, 'devices'):
                for device in app_settings.devices:
                    device_dict = device.model_dump()
                    devices_config.append(device_dict)

            if devices_config:
                device_manager.load_devices_from_config(devices_config)
                logger.info(f"Loaded {len(device_manager.get_all_devices())} devices")
            else:
                logger.warning("No devices found in configuration")

        except Exception as e:
            logger.error(f"Failed to load devices: {e}")
            if app_settings.environment.value == "production":
                raise
            else:
                logger.warning("Continuing without devices in development mode")

        # Step 5: Configure LLM control if enabled
        if app_settings.zhipuai.enabled and app_settings.zhipuai.api_key:
            try:
                device_manager.enable_llm_control(app_settings.zhipuai.api_key)
                logger.info("LLM control enabled with ZhipuAI")
            except Exception as e:
                logger.error(f"Failed to enable LLM control: {e}")
                if app_settings.environment.value == "production":
                    raise
                else:
                    logger.warning("Continuing without LLM control in development mode")

        # Step 6: Store settings in app state for API access
        app.state.app_settings = app_settings
        app.state.device_manager = device_manager

        # Step 7: Perform health check
        validation_service = get_validation_service()
        health_result = validation_service.perform_health_check(app_settings)

        if health_result.is_valid:
            logger.info("Application health check passed")
        else:
            logger.warning(f"Health check warnings: {health_result.warnings}")

        logger.info(f"SynHome application started successfully on {app_settings.host}:{app_settings.port}")
        logger.info(f"Environment: {app_settings.environment.value}")
        logger.info(f"Debug mode: {app_settings.debug}")

        yield  # Application is running

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    finally:
        # Cleanup on shutdown
        logger.info("Shutting down SynHome application...")

        if device_manager:
            try:
                # Disconnect all adapters
                if hasattr(device_manager, "adapters"):
                    for adapter_id, adapter in device_manager.adapters.items():
                        logger.info(f"Disconnecting adapter: {adapter_id}")
                        await adapter.disconnect()
                    logger.info("All adapters disconnected")
            except Exception as e:
                logger.error(f"Error during adapter cleanup: {e}")

        logger.info("SynHome application shutdown complete")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="SynHome Smart Home Control System",
    description="Smart home device control with LLM integration",
    version="2.0.0",
    lifespan=lifespan
)

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add debug middleware in development mode
def get_app_settings():
    """Get app settings from app state or return None if not initialized"""
    return getattr(app.state, 'app_settings', None)

# Add debug middleware only in development
settings = get_app_settings()
if settings and settings.debug:
    app.add_middleware(DebugMiddleware)

class CommandRequest(BaseModel):
    command: str
    device_id: Optional[str] = None

# Set up static files
static_dir = Path(__file__).parent / "web"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

@app.get("/")
async def root():
    """Serve the main page"""
    logger = get_logger("api")
    logger.info("Serving index page")

    if static_dir.exists():
        return FileResponse(static_dir / "index.html")
    else:
        return JSONResponse(
            content={"message": "SynHome API is running", "version": "2.0.0"},
            status_code=200
        )

@app.get("/devices")
async def list_devices():
    """Get list of all devices"""
    api_logger = get_logger("api")
    try:
        # Get device manager from app state
        device_manager = getattr(app.state, 'device_manager', None)
        if not device_manager:
            raise HTTPException(status_code=503, detail="Device manager not initialized")

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

        api_logger.info(f"Returning {len(device_list)} devices")
        return JSONResponse(
            content=jsonable_encoder(device_list),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-cache"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Error listing devices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/devices/{device_id}/command")
async def send_command_to_device(device_id: str, command: CommandRequest):
    """Send command to specific device"""
    api_logger = get_logger("api")
    try:
        api_logger.info(f"Received command for device {device_id}: {command.command}")

        # Get device manager from app state
        device_manager = getattr(app.state, 'device_manager', None)
        if not device_manager:
            raise HTTPException(status_code=503, detail="Device manager not initialized")

        device = device_manager.get_device_by_id(device_id)
        if not device:
            api_logger.warning(f"Device not found: {device_id}")
            raise HTTPException(status_code=404, detail="Device not found")

        if not device.process_natural_command(command.command):
            api_logger.warning("Command processing failed")
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
        api_logger.error(f"Error executing command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/command")
async def process_global_command(command: CommandRequest):
    """Process a command without specifying device"""
    api_logger = get_logger("api")
    try:
        api_logger.info(f"Received global command: {command.command}")

        # Get device manager from app state
        device_manager = getattr(app.state, 'device_manager', None)
        if not device_manager:
            raise HTTPException(status_code=503, detail="Device manager not initialized")

        result = device_manager.process_command(command.command, command.device_id)
        if not result["success"]:
            api_logger.warning(f"Command processing failed: {result['message']}")
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

# Configuration API endpoints
@app.get("/api/v1/config")
async def get_configuration():
    """Get current application configuration"""
    api_logger = get_logger("api")
    try:
        app_settings = getattr(app.state, 'app_settings', None)
        if not app_settings:
            raise HTTPException(status_code=503, detail="Configuration not loaded")

        # Return configuration without sensitive data
        config_dict = app_settings.model_dump(exclude={"zhipuai": {"api_key"}})

        api_logger.info("Configuration retrieved")
        return JSONResponse(
            content=jsonable_encoder(config_dict),
            headers={"Cache-Control": "no-cache"}
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Error getting configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/config/health")
async def get_configuration_health():
    """Get configuration health status"""
    api_logger = get_logger("api")
    try:
        app_settings = getattr(app.state, 'app_settings', None)
        if not app_settings:
            raise HTTPException(status_code=503, detail="Configuration not loaded")

        validation_service = get_validation_service()
        health_result = validation_service.perform_health_check(app_settings)

        api_logger.info("Configuration health check completed")
        return JSONResponse(
            content={
                "status": "healthy" if health_result.is_valid else "unhealthy",
                "errors": health_result.errors,
                "warnings": health_result.warnings,
                "validation_time_ms": health_result.validation_time_ms
            },
            headers={"Cache-Control": "no-cache"}
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Error during health check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/config/validate")
async def validate_configuration_data(config_data: Dict[str, Any]):
    """Validate configuration data"""
    api_logger = get_logger("api")
    try:
        validation_service = get_validation_service()
        result = validation_service.validate_configuration_data(config_data, "api_validation")

        api_logger.info(f"Configuration validation completed: {result.status.value}")
        return JSONResponse(
            content={
                "status": result.status.value,
                "is_valid": result.is_valid,
                "errors": result.errors,
                "warnings": result.warnings,
                "validation_time_ms": result.validation_time_ms
            },
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        api_logger.error(f"Error validating configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/config/info")
async def get_device_info():
    """Get device configuration information"""
    api_logger = get_logger("api")
    try:
        app_settings = getattr(app.state, 'app_settings', None)
        if not app_settings:
            raise HTTPException(status_code=503, detail="Configuration not loaded")

        device_types = set()
        capabilities = {}

        # Get device configurations from app settings
        if hasattr(app_settings, 'devices'):
            for device in app_settings.devices:
                device_types.add(device.type)

                for cap_name, cap_config in device.capabilities.items():
                    if cap_name not in capabilities:
                        capabilities[cap_name] = {
                            "type": cap_config.type,
                            "values": cap_config.values if cap_config.type == "enum" else None,
                            "unit": cap_config.unit if cap_config.type == "number" else None,
                            "min_value": cap_config.min_value if hasattr(cap_config, 'min_value') else None,
                            "max_value": cap_config.max_value if hasattr(cap_config, 'max_value') else None
                        }

        api_logger.info("Device info retrieved")
        return JSONResponse(
            content=jsonable_encoder({
                "device_types": list(device_types),
                "capabilities": capabilities,
                "total_devices": len(app_settings.devices) if hasattr(app_settings, 'devices') else 0
            }),
            headers={"Cache-Control": "no-cache"}
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Error getting device info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/status")
async def get_application_status():
    """Get application status"""
    api_logger = get_logger("api")
    try:
        app_settings = getattr(app.state, 'app_settings', None)
        device_manager = getattr(app.state, 'device_manager', None)

        status = {
            "application": "SynHome",
            "version": "2.0.0",
            "environment": app_settings.environment.value if app_settings else "unknown",
            "debug": app_settings.debug if app_settings else False,
            "configuration_loaded": app_settings is not None,
            "device_manager_initialized": device_manager is not None,
            "device_count": len(device_manager.get_all_devices()) if device_manager else 0,
            "llm_enabled": app_settings.zhipuai.enabled if app_settings else False,
            "uptime_seconds": None  # Could be implemented with uptime tracking
        }

        api_logger.info("Application status retrieved")
        return JSONResponse(
            content=jsonable_encoder(status),
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        api_logger.error(f"Error getting application status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment or use defaults
    config_file = os.getenv("SYNHOME_CONFIG_FILE", "config/demo.yaml")
    host = os.getenv("SYNHOME_HOST", "0.0.0.0")
    port = int(os.getenv("SYNHOME_PORT", "8000"))
    log_level = os.getenv("SYNHOME_LOG_LEVEL", "info")

    print(f"Starting SynHome server...")
    print(f"Config file: {config_file}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Log level: {log_level}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=True
    )