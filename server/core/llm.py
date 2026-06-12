"""LLM 统一网关 — 多提供商路由、故障切换"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator

from openai import AsyncOpenAI

from server.config import settings

logger = logging.getLogger(__name__)


# ── 响应数据 ──


@dataclass
class LLMResponse:
    """LLM 调用结果"""

    content: str = ""
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    latency_ms: int = 0


# ── 任务→模型映射 ──

TASK_MODEL_MAP: dict[str, dict[str, str]] = {
    "deepseek": {
        "classification": "deepseek-chat",
        "analysis": "deepseek-chat",
        "explanation": "deepseek-chat",
        "scoring": "deepseek-chat",
    },
    "openai": {
        "classification": "gpt-4o-mini",
        "analysis": "gpt-4o",
        "explanation": "gpt-4o-mini",
        "scoring": "gpt-4o",
    },
}

# 提供商优先级（故障切换顺序）
PROVIDER_PRIORITY = ["deepseek", "openai"]


# ── 网关 ──


class LLMGateway:
    """LLM 统一网关，支持多提供商、多模型、故障切换"""

    def __init__(self) -> None:
        self._clients: dict[str, AsyncOpenAI] = {}
        self._init_clients()

    def _init_clients(self) -> None:
        """初始化各提供商的 OpenAI 兼容客户端"""
        providers_config = {
            "deepseek": {
                "api_key": settings.LLM_DEEPSEEK_API_KEY,
                "base_url": "https://api.deepseek.com/v1",
            },
            "openai": {
                "api_key": settings.LLM_OPENAI_API_KEY,
                "base_url": "https://api.openai.com/v1",
            },
        }
        for name, cfg in providers_config.items():
            if cfg["api_key"]:
                self._clients[name] = AsyncOpenAI(
                    api_key=cfg["api_key"],
                    base_url=cfg["base_url"],
                    timeout=120.0,
                )
                logger.info("LLM 提供商已初始化: %s", name)

        # Ollama（本地模型）
        if settings.OLLAMA_ENDPOINT:
            self._clients["ollama"] = AsyncOpenAI(
                api_key="ollama",
                base_url=settings.OLLAMA_ENDPOINT + "/v1",
                timeout=300.0,
            )
            logger.info("LLM 本地模型已初始化: ollama")

    def _get_model(self, provider: str, task: str) -> str:
        """获取指定提供商+任务对应的模型名"""
        task_map = TASK_MODEL_MAP.get(provider, {})
        return task_map.get(task, "deepseek-chat")

    def _get_available_providers(self) -> list[str]:
        """返回有 API Key 的提供商列表"""
        return [p for p in PROVIDER_PRIORITY if p in self._clients]

    async def chat(
        self,
        messages: list[dict],
        task: str,
        temperature: float = 0.1,
        max_retries: int = 2,
    ) -> LLMResponse:
        """
        调用 LLM API，支持重试和故障切换。

        故障切换逻辑：
        主模型失败 → 重试（换 temperature）→ 再失败 → 切换备用模型 → 再失败 → 返回错误
        """
        providers = self._get_available_providers()
        if not providers:
            logger.error("没有可用的 LLM 提供商，请检查 API Key 配置")
            return LLMResponse(content="", model="", provider="", tokens_used=0, latency_ms=0)

        last_error: Exception | None = None

        for provider in providers:
            client = self._clients.get(provider)
            if not client:
                continue

            model = self._get_model(provider, task)

            for attempt in range(max_retries + 1):
                temp = temperature if attempt == 0 else min(temperature + 0.1 * attempt, 0.9)
                start = time.monotonic()
                try:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temp,
                    )
                    latency = int((time.monotonic() - start) * 1000)
                    content = response.choices[0].message.content or ""
                    tokens = response.usage.total_tokens if response.usage else 0

                    logger.info(
                        "LLM 调用成功: provider=%s model=%s task=%s latency=%dms tokens=%d",
                        provider, model, task, latency, tokens,
                    )
                    return LLMResponse(
                        content=content.strip(),
                        model=model,
                        provider=provider,
                        tokens_used=tokens,
                        latency_ms=latency,
                    )
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "LLM 调用失败: provider=%s model=%s attempt=%d error=%s",
                        provider, model, attempt + 1, str(e),
                    )
                    # 重试前短暂等待
                    if attempt < max_retries:
                        await asyncio.sleep(1.0 * (attempt + 1))

            # 当前提供商所有重试用完，切换下一个
            logger.warning("提供商 %s 所有重试用完，尝试切换备用", provider)

        logger.error("所有 LLM 提供商均失败: %s", last_error)
        return LLMResponse(content="", model="", provider="", tokens_used=0, latency_ms=0)

    async def chat_stream(
        self,
        messages: list[dict],
        task: str,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """流式输出，用于 WebSocket 实时推送"""
        providers = self._get_available_providers()
        if not providers:
            yield ""
            return

        provider = providers[0]
        client = self._clients.get(provider)
        if not client:
            yield ""
            return

        model = self._get_model(provider, task)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("LLM 流式调用失败: %s", e)
            yield ""

    def parse_json(self, content: str) -> dict | list | None:
        """从 LLM 输出中提取 JSON，容错处理"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { ... } 或 [ ... ]
        for opener, closer in [("{", "}"), ("[", "]")]:
            start = content.find(opener)
            end = content.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass

        logger.warning("无法从 LLM 输出中解析 JSON: %s", content[:200])
        return None


# 全局单例
llm_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    """获取或创建 LLM 网关单例"""
    global llm_gateway
    if llm_gateway is None:
        llm_gateway = LLMGateway()
    return llm_gateway
