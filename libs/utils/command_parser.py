#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command Parser for handling complex commands involving multiple devices and operations
"""

import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class CommandParser:
    """
    Parser for complex smart home commands
    """
    
    @staticmethod
    def detect_command_type(command: str) -> str:
        """
        Detect command type based on command text
        
        Args:
            command: Natural language command
            
        Returns:
            Command type: 'single_device', 'multi_device', 'group', 'scene', or 'unknown'
        """
        # Pattern matchers for different command types
        multi_device_patterns = [
            r'所有|全部|每个|每一个',  # Chinese keywords for "all" or "every"
            r'全部设备|所有设备|所有的设备',  # "all devices" in Chinese
            r'all devices|every device|all',  # English
            r'\w+和\w+',  # "X和Y" pattern in Chinese
            r'\w+ and \w+'  # "X and Y" pattern in English
        ]
        
        group_patterns = [
            r'群组|分组|设备组|房间',  # Group related terms in Chinese
            r'group|room'  # Group related terms in English
        ]
        
        scene_patterns = [
            r'场景|模式|情景',  # Scene related terms in Chinese
            r'scene|mode|scenario'  # Scene related terms in English
        ]
        
        # Check if command matches multi-device pattern
        for pattern in multi_device_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return 'multi_device'
        
        # Check if command matches group pattern
        for pattern in group_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return 'group'
                
        # Check if command matches scene pattern
        for pattern in scene_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return 'scene'
        
        # Default to single device if no other pattern matches
        return 'single_device'
    
    @staticmethod
    def extract_devices_from_command(command: str, device_names: List[str]) -> List[str]:
        """
        Extract device names from command
        
        Args:
            command: Natural language command
            device_names: List of available device names
            
        Returns:
            List of device names found in command
        """
        found_devices = []
        
        # Special case for "all" devices
        all_device_patterns = [
            r'所有|全部|每个|每一个',  # Chinese
            r'all devices|every device|all'  # English
        ]
        
        for pattern in all_device_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return ["ALL"]  # Special marker for all devices
        
        # Check for specific devices mentioned in the command
        for device_name in device_names:
            if device_name in command:
                found_devices.append(device_name)
                
        return found_devices
    
    @staticmethod
    def detect_multi_device_operations(command: str) -> bool:
        """
        检测命令是否包含针对多个不同设备的操作
        
        Args:
            command: 自然语言命令
            
        Returns:
            是否是跨设备多操作命令
        """
        # 跨设备操作的常见模式 - 使用逗号、顿号、和/与等分隔不同设备操作
        separators = [',', '，', '、', '和', '与', 'and']
        
        # 设备类型关键词
        device_keywords = {
            '灯': 'light',
            '照明': 'light',
            '空调': 'thermostat',
            '温度': 'thermostat',
            '制热': 'thermostat',
            '制冷': 'thermostat',
            '电饭煲': 'rice_cooker',
            '煮饭': 'rice_cooker',
            '饭': 'rice_cooker',
            '窗帘': 'curtain',
            '插座': 'socket',
            '扫地机': 'vacuum'
        }
        
        # 检测是否包含分隔符
        has_separator = any(sep in command for sep in separators)
        if not has_separator:
            return False
            
        # 检测是否提及多种设备类型
        device_types_found = set()
        for keyword, device_type in device_keywords.items():
            if keyword in command:
                device_types_found.add(device_type)
                
        # 如果发现多种设备类型，且有分隔符，认为是跨设备命令
        return len(device_types_found) > 1
    
    @staticmethod
    def split_multi_device_command(command: str, device_types: List[str]) -> Dict[str, str]:
        """
        将跨设备命令拆分为针对各设备的子命令
        
        Args:
            command: 自然语言命令
            device_types: 系统中所有可用的设备类型
            
        Returns:
            按设备类型分组的子命令
        """
        # 设备关键词到设备类型的映射
        device_keywords = {
            'light': ['灯', '照明', '亮', '灯光', '亮度'],
            'thermostat': ['空调', '温度', '制热', '制冷', '暖气', '冷气', '风速', '风量'],
            'rice_cooker': ['电饭煲', '饭', '煮饭', '煲饭', '煮粥', '煲汤'],
            'curtain': ['窗帘', '窗户'],
            'vacuum': ['扫地机', '吸尘器', '打扫'],
            'socket': ['插座', '插头', '电源']
        }
        
        # 可能的命令分隔符
        separators = [',', '，', '、', '。', ';', '；']
        
        # 1. 先尝试基于标点符号拆分命令
        segments = []
        current_segment = ""
        for char in command:
            current_segment += char
            if char in separators:
                segments.append(current_segment.strip())
                current_segment = ""
        if current_segment:  # 添加最后一段
            segments.append(current_segment.strip())
            
        if not segments:  # 如果没有找到分隔符
            segments = [command]
            
        # 2. 为每个子命令确定目标设备类型
        device_commands = {}
        for segment in segments:
            target_type = None
            max_matches = 0
            
            # 为每个设备类型计算关键词匹配度
            for d_type, keywords in device_keywords.items():
                matches = sum(1 for keyword in keywords if keyword in segment)
                if matches > max_matches:
                    max_matches = matches
                    target_type = d_type
                    
            # 如果找到目标设备类型，添加到结果
            if target_type:
                if target_type not in device_commands:
                    device_commands[target_type] = []
                device_commands[target_type].append(segment)
        
        # 3. 合并同一设备类型的多个命令片段
        result = {}
        for d_type, cmd_segments in device_commands.items():
            result[d_type] = "，".join(cmd_segments)
            
        return result
