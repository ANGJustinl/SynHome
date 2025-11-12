#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ZhipuAI LangChain Adapter

将现有的ZhipuAI客户端适配为LangChain的LLM接口
"""

from typing import Any, Dict, List, Optional, Union, Iterator, AsyncIterator
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.language_models.llms import BaseLLM
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import LLMResult, Generation, ChatGeneration, ChatResult
from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
import logging

from ..utils.llm import ZhipuAIClient

logger = logging.getLogger(__name__)


class ZhipuAILangChainAdapter(BaseLLM):
    """
    ZhipuAI LangChain适配器

    将现有的ZhipuAIClient包装为LangChain兼容的LLM接口
    """

    zhipuai_client: ZhipuAIClient

    def __init__(
        self,
        api_key: str,
        model: str = "glm-4.5-air",
        temperature: float = 0.2,
        **kwargs
    ):
        """初始化ZhipuAI适配器"""
        super().__init__(temperature=temperature, **kwargs)
        self.zhipuai_client = ZhipuAIClient(api_key=api_key, model=model)

    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """生成响应"""
        generations = []

        for prompt in prompts:
            try:
                # 构建LangChain消息格式
                messages = [
                    {"role": "system", "content": "You are a helpful smart home assistant."},
                    {"role": "user", "content": prompt}
                ]

                # 调用ZhipuAI
                response = self.zhipuai_client.chat(
                    messages=messages,
                    temperature=self.temperature,
                    **kwargs
                )

                if response:
                    generations.append([Generation(text=response)])
                else:
                    generations.append([Generation(text="")])

            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                generations.append([Generation(text="")])

        return LLMResult(generations=generations)

    async def _agenerate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """异步生成响应"""
        return self._generate(prompts, stop, run_manager, **kwargs)

    @property
    def _llm_type(self) -> str:
        """返回LLM类型"""
        return "zhipuai"

    def _identify_purpose_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """识别参数的目的"""
        return {
            "api_key": "ZhipuAI API密钥，用于认证",
            "model": "使用的ZhipuAI模型，如glm-4-plus",
            "temperature": "控制响应的随机性，0-1之间",
            **params
        }


class ZhipuAIChatAdapter:
    """
    ZhipuAI聊天适配器

    专门处理智能家居控制对话的适配器
    """

    def __init__(self, api_key: str, model: str = "glm-4.5-air"):
        """初始化聊天适配器"""
        self.zhipuai_client = ZhipuAIClient(api_key=api_key, model=model)

    def analyze_device_command(
        self,
        device_type: str,
        current_state: Dict[str, Any],
        command: str,
        memory_context: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        增强的设备命令分析，包含记忆上下文

        Args:
            device_type: 设备类型
            current_state: 设备当前状态
            command: 用户命令
            memory_context: 来自记忆系统的上下文信息

        Returns:
            解析后的命令和参数
        """
        try:
            # 构建增强的系统提示
            system_prompt = self._build_enhanced_system_prompt(
                device_type, current_state, memory_context
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Control command: {command}"}
            ]

            response = self.zhipuai_client.chat(messages)

            if response:
                # 这里需要实现与现有相同的JSON解析逻辑
                # 为了简化，暂时返回基本响应
                return {"command": command, "raw_response": response}

            return None

        except Exception as e:
            logger.error(f"Error analyzing device command with memory: {str(e)}")
            return None

    def _build_enhanced_system_prompt(
        self,
        device_type: str,
        current_state: Dict[str, Any],
        memory_context: Optional[str]
    ) -> str:
        """构建增强的系统提示"""
        base_prompt = f"""You are a smart home control assistant that translates natural language commands to device control instructions.

Device Type: {device_type}
Device Name: {current_state.get("device_name")}
Current State: {current_state.get("current_state", "UNKNOWN")}

Device Capabilities:
"""

        # 添加设备能力信息
        capabilities = current_state.get("capabilities", {})
        for name, info in capabilities.items():
            cap_type = info.get("type")
            current = info.get("current_value")

            if cap_type == "switch":
                states = info.get("states", ["on", "off"])
                base_prompt += f"{name}: 开关类型, 可选值:{'/'.join(states)}, 当前:{current}\n"
            elif cap_type == "number":
                min_val = info.get("min")
                max_val = info.get("max")
                unit = info.get("unit", "")
                base_prompt += f"{name}: 数值类型, 范围:{min_val}-{max_val}{unit}, 当前:{current}{unit}\n"
            elif cap_type == "enum":
                values = info.get("values", [])
                base_prompt += f"{name}: 枚举类型, 可选值:{'/'.join(values)}, 当前:{current}\n"

        # 添加记忆上下文
        if memory_context:
            base_prompt += f"""

User Context (from memory):
{memory_context}

Based on this context, consider the user's habits and preferences when interpreting the command.
"""

        base_prompt += """
Response Instructions:
- Analyze the user's intent considering their habits
- Return device control instructions in JSON format
- Include suggestions based on learned preferences
- Consider time of day and typical usage patterns
"""

        return base_prompt