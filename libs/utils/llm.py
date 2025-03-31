#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ZhipuAI Client
Wrapper for zhipuai SDK to provide LLM capabilities
"""

import logging
import json
from typing import Dict, Any, List, Optional
from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)


class ZhipuAIClient:
    """Wrapper class for zhipuai SDK"""
    
    def __init__(self, api_key: str, model: str = "glm-4-plus"):
        """
        Initialize ZhipuAI client
        
        Args:
            api_key: ZhipuAI API key
            model: Model name to use (default: glm-4-plus)
        """
        self.api_key = api_key
        self.client = ZhipuAI(api_key=api_key)
        self.model = model
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        Send chat messages to ZhipuAI
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Response text if successful, None if failed
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,  # 使用较低的温度以获得更稳定的输出
                **kwargs
            )
            
            if response and response.choices:
                return response.choices[0].message.content
            else:
                logger.error(f"ZhipuAI API error: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling ZhipuAI API: {str(e)}")
            return None
            
    def analyze_device_control(self, device_type: str, current_state: Dict[str, Any], 
                             command: str) -> Optional[Dict[str, Any]]:
        """
        分析设备控制命令
        
        Args:
            device_type: 设备类型
            current_state: 设备当前状态
            command: 自然语言命令
            
        Returns:
            Dict with parsed command and parameters if successful,
            None if failed
        """
        # 提取设备能力，为LLM提供更清晰的上下文
        capabilities = current_state.get("capabilities", {})
        cap_info = []
        
        # 构建每个能力的描述
        for name, info in capabilities.items():
            cap_type = info.get("type")
            current = info.get("current_value")
            
            if cap_type == "switch":
                states = info.get("states", ["on", "off"])
                cap_info.append(f"{name}: 开关类型, 可选值:{'/'.join(states)}, 当前:{current}")
            elif cap_type == "number":
                min_val = info.get("min")
                max_val = info.get("max")
                unit = info.get("unit", "")
                cap_info.append(f"{name}: 数值类型, 范围:{min_val}-{max_val}{unit}, 当前:{current}{unit}")
            elif cap_type == "enum":
                values = info.get("values", [])
                cap_info.append(f"{name}: 枚举类型, 可选值:{'/'.join(values)}, 当前:{current}")
        
        # 动态生成设备命令模板
        device_template = self._generate_command_template(device_type, capabilities)
        
        # 修改提示信息，更明确地指导LLM如何处理复合命令
        system_prompt = f"""You are a smart home control assistant that translates natural language commands to device control instructions.

Device Type: {device_type}
Device Name: {current_state.get("device_name")}
Current State: {current_state.get("current_state", "UNKNOWN")}

Device Capabilities:
{chr(10).join(cap_info)}

{device_template}

Response Instructions:
1. Analyze if the command contains multiple actions (compound command)
2. For COMPOUND COMMANDS with multiple actions like "turn up temperature and switch to heating mode":
   - Return: {{"compound": true, "operations": [{{"command": "set_temperature", "params": {{"temperature": 26}}}}, {{"command": "set_mode", "params": {{"mode": "heat"}}}}]}}

3. For SIMPLE COMMANDS with a single action:
   - Return: {{"command": "set_temperature", "params": {{"temperature": 25}}}}

4. IMPORTANT: Always include "command" field in your JSON response
5. Parameter values must be within the specified ranges
6. Output ONLY valid JSON with no additional text"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Control command: {command}"}
        ]
        
        response = self.chat(messages)
        if not response:
            return None
            
        try:
            # 清理响应文本，提取JSON
            response = response.strip()
            # 记录原始响应以便调试
            logger.debug(f"Raw LLM response: {response}")
            
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > 0:
                response = response[start:end]
                
            # 尝试解析JSON
            parsed = json.loads(response)
            
            # 检查是否是复合命令
            if "compound" in parsed and parsed.get("compound") == True and "operations" in parsed:
                logger.info(f"Detected compound command with {len(parsed['operations'])} operations")
                # 确保每个操作都有command字段
                for i, op in enumerate(parsed["operations"]):
                    if "command" not in op:
                        logger.warning(f"Operation {i} is missing command field: {op}")
                        if "params" in op and len(op["params"]) == 1:
                            # 尝试修复：使用参数名作为命令
                            param_name = next(iter(op["params"].keys()))
                            op["command"] = f"set_{param_name}"
                            logger.info(f"Fixed operation: {op}")
                return parsed
            
            # 如果不是复合命令，验证基本结构
            if "command" not in parsed:
                # 尝试推断命令
                if "params" in parsed and isinstance(parsed["params"], dict):
                    # 情况1：命令隐含在参数中
                    param_keys = list(parsed["params"].keys())
                    if len(param_keys) == 1:
                        param_name = param_keys[0]
                        # 将参数名转换为命令
                        parsed["command"] = f"set_{param_name}"
                        logger.warning(f"Inferred command from parameter: {parsed}")
                        return parsed
                
                # 情况2：整个响应就是参数集合
                for key in parsed:
                    if key in capabilities:
                        # 构建一个新的标准格式响应
                        inferred = {
                            "command": f"set_{key}",
                            "params": {key: parsed[key]}
                        }
                        logger.warning(f"Constructed command from direct parameter: {parsed} -> {inferred}")
                        return inferred
                
                # 情况3：尝试解析为复合命令
                if isinstance(parsed, dict) and len(parsed) > 1:
                    operations = []
                    for key, value in parsed.items():
                        if key in capabilities:
                            operations.append({
                                "command": f"set_{key}",
                                "params": {key: value}
                            })
                    
                    if operations:
                        compound_cmd = {
                            "compound": True,
                            "operations": operations
                        }
                        logger.warning(f"Converted to compound command: {parsed} -> {compound_cmd}")
                        return compound_cmd
                
                # 如果都失败了，记录错误
                logger.error(f"Invalid response format from LLM (missing command): {parsed}")
                return None
                
            logger.info(f"Successfully parsed command: {parsed}")
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}, response was: {response}")
            return None
            
    def _generate_command_template(self, device_type: str, capabilities: Dict[str, Any]) -> str:
        """
        根据设备类型和能力动态生成命令模板
        
        Args:
            device_type: 设备类型
            capabilities: 设备能力信息
            
        Returns:
            命令模板字符串
        """
        template_lines = ["AVAILABLE COMMANDS:"]
        
        # 1. Add common power command
        if "power" in capabilities:
            template_lines.append("- Power control: {\"command\": \"on\"} or {\"command\": \"off\"}")
        
        # 2. Add specific commands based on device capabilities
        for name, info in capabilities.items():
            cap_type = info.get("type")
            
            if cap_type == "switch" and name != "power":
                template_lines.append(f"- Set {name}: {{\"command\": \"set_{name}\", \"params\": {{\"{name}\": \"on/off\"}}}}")
                
            elif cap_type == "number":
                min_val = info.get("min")
                max_val = info.get("max")
                unit = info.get("unit", "")
                template_lines.append(f"- Set {name}: {{\"command\": \"set_{name}\", \"params\": {{\"{name}\": {min_val}-{max_val}{unit}}}}}")
                
            elif cap_type == "enum":
                values = info.get("values", [])
                values_str = "/".join([f"\"{v}\"" for v in values])
                template_lines.append(f"- Set {name}: {{\"command\": \"set_{name}\", \"params\": {{\"{name}\": {values_str}}}}}")
        
        # 3. Add device-specific special commands
        if device_type == "thermostat":
            template_lines.append("- Set multiple parameters: {\"command\": \"set_mode\", \"params\": {\"mode\": \"value\", \"fan_speed\": \"value\", \"temperature\": value}}")
        
        elif device_type == "rice_cooker":
            template_lines.append("- Start cooking: {\"command\": \"start_cooking\", \"params\": {\"program\": \"program_name\"}}")
            template_lines.append("- Stop cooking: {\"command\": \"stop\"}")
        
        elif device_type == "vacuum":
            template_lines.append("- Start cleaning: {\"command\": \"start\", \"params\": {\"mode\": \"cleaning_mode\"}}")
            template_lines.append("- Stop cleaning: {\"command\": \"stop\"}")
        
        # 更新复合命令示例，提供更具体的参考
        template_lines.append("\nCOMPOUND COMMAND FORMAT:")
        template_lines.append("""For commands with multiple actions (e.g., "increase temperature and set to heating mode"), use this format:

{
  "compound": true,
  "operations": [
    {"command": "set_temperature", "params": {"temperature": 26}},
    {"command": "set_mode", "params": {"mode": "heat"}}
  ]
}

EXAMPLE INPUT: "Turn up the temperature and switch to heating mode"
CORRECT OUTPUT: {"compound": true, "operations": [{"command": "set_temperature", "params": {"temperature": 26}}, {"command": "set_mode", "params": {"mode": "heat"}}]}""")
        template_lines.append("IMPORTANT: Each operation MUST include a 'command' field.")
        
        return "\n".join(template_lines)