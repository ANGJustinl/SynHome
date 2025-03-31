#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration loader utility
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Configuration loader class"""
    
    def __init__(self, config_path: str):
        """Initialize with config file path"""
        self.config_path = config_path
        
    def load(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            # Convert to absolute path if relative
            if not os.path.isabs(self.config_path):
                base_path = Path(__file__).parent.parent.parent
                config_path = base_path / self.config_path
            else:
                config_path = Path(self.config_path)
                
            # Check if file exists
            if not config_path.exists():
                logger.error(f"配置文件不存在: {self.config_path}")
                raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
            
            # Load and parse YAML
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            logger.info(f"成功加载配置文件: {self.config_path}")
            return config
            
        except yaml.YAMLError as e:
            logger.error(f"YAML解析错误: {str(e)}")
            raise
        
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            raise
