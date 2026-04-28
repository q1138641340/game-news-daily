"""
LLM 调用封装工具
支持 Kimi (moonshot)、DeepSeek V4、MiniMax，统一接口

模型分配:
- 收集阶段: MiniMax-M2.7-highspeed (快速、便宜)
- 审查阶段: Kimi-2.5 (复杂推理)
- 整理阶段: DeepSeek V4 Pro (生成)
"""

from openai import OpenAI
from typing import Optional
from dotenv import load_dotenv
import os
import httpx

load_dotenv()


# 预配置的模型
class Models:
    # 收集阶段 (快速模型 - MiniMax + DeepSeek Flash)
    COLLECT_MINIMAX = "MiniMax-M2.7-highspeed"
    COLLECT_DEEPSEEK_FLASH = "deepseek-v4-flash"

    # 审查阶段 (高精度模型 - Kimi)
    REVIEW_KIMI = "moonshot-v1-32k"

    # 整理阶段 (生成模型 - DeepSeek Pro)
    FORMAT_DEEPSEEK_PRO = "deepseek-chat"


class LLMClient:
    """统一的 LLM 客户端"""

    def __init__(self, provider: str = "deepseek"):
        """
        初始化 LLM 客户端

        Args:
            provider: "kimi" 或 "deepseek"
        """
        self.provider = provider

        if provider == "kimi":
            self.client = OpenAI(
                api_key=os.getenv("KIMI_API_KEY"),
                base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
            )
            self.default_model = "moonshot-v1-32k"
        elif provider == "deepseek":
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            )
            self.default_model = "deepseek-chat"
        elif provider == "minimax":
            # MiniMax API，OpenAI 兼容端点
            import httpx
            timeout = httpx.Timeout(60.0, connect=30.0)
            http_client = httpx.Client(timeout=timeout, follow_redirects=True)
            self.client = OpenAI(
                api_key=os.getenv("MINIMAX_API_KEY"),
                base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
                http_client=http_client
            )
            self.default_model = "MiniMax-M2.7-highspeed"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """
        发送对话请求

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            model: 模型名称（可选，默认使用客户端的默认模型）
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            模型回复文本
        """
        model = model or self.default_model

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        return response.choices[0].message.content

    def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3
    ) -> dict | list:
        """
        发送对话请求并期望返回 JSON

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            model: 模型名称
            temperature: 温度参数（建议用低值以获得更稳定输出）

        Returns:
            解析后的 JSON 对象
        """
        from tools.json_parser import parse_json

        response = self.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            temperature=temperature
        )

        return parse_json(response)


# 便捷函数：按用途获取对应的客户端和模型


def get_collect_minimax() -> tuple[LLMClient, str]:
    """收集阶段 MiniMax-M2.7-highspeed 客户端"""
    client = LLMClient(provider="minimax")
    return client, Models.COLLECT_MINIMAX


def get_collect_deepseek_flash() -> tuple[LLMClient, str]:
    """收集阶段 DeepSeek V4 Flash 客户端"""
    client = LLMClient(provider="deepseek")
    return client, Models.COLLECT_DEEPSEEK_FLASH


def get_collect_deepseek() -> tuple[LLMClient, str]:
    """预处理阶段 DeepSeek V4 Pro 客户端"""
    client = LLMClient(provider="deepseek")
    return client, Models.FORMAT_DEEPSEEK_PRO


def get_review_kimi() -> tuple[LLMClient, str]:
    """审查阶段 Kimi-2.5 客户端"""
    client = LLMClient(provider="kimi")
    return client, Models.REVIEW_KIMI


def get_format_deepseek() -> tuple[LLMClient, str]:
    """整理阶段 DeepSeek V4 Pro 客户端"""
    client = LLMClient(provider="deepseek")
    return client, Models.FORMAT_DEEPSEEK_PRO


# 向后兼容
def get_kimi_client() -> LLMClient:
    """获取 Kimi 客户端"""
    return LLMClient(provider="kimi")


def get_deepseek_client() -> LLMClient:
    """获取 DeepSeek 客户端（默认 DeepSeek V4）"""
    return LLMClient(provider="deepseek")
