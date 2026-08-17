"""LLM 统一网关 — 多提供商路由、故障切换"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import AsyncGenerator, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from server.config import settings

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)


# ── 响应数据 ──


@dataclass
class LLMResponse:
    """LLM 调用结果"""

    content: str = ""
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    latency_ms: int = 0


@dataclass
class StructuredLLMResponse(LLMResponse):
    """结构化 LLM 调用结果"""

    parsed: BaseModel | None = None
    via: str = "fallback"  # outlines | json_schema | fallback


# ── 硬编码映射（仅作 fallback，优先级最低） ──

_TASK_MODEL_FALLBACK: dict[str, dict[str, str]] = {
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

# 任务名 → 配置文件中 models 字段的 key 映射
_TASK_TO_CONFIG_KEY: dict[str, str] = {
    "classification": "classify",
    "analysis": "analyze",
    "explanation": "explain",
    "scoring": "analyze",       # 评分用 analyze 模型
}


# ── 深合并工具 ──


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深合并：override 中的值覆盖 base，缺失的键从 base 补齐"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ── 网关 ──


class LLMGateway:
    """LLM 统一网关，支持多提供商、多模型、故障切换"""

    def __init__(self) -> None:
        self._clients: dict[str, AsyncOpenAI] = {}
        self._config: dict = {}
        # 记录不支持 json_schema response_format 的 (provider, model)，后续跳过 Outlines
        self._structured_unsupported: set[tuple[str, str]] = set()
        self._init_clients()

    # ── 配置加载 ──

    def _load_config_from_file(self) -> dict:
        """从配置文件加载 LLM 设置"""
        config_file = os.path.join("data", "llm_config.json")
        default_config = {
            "remote": {
                "enabled": bool(settings.LLM_DEEPSEEK_API_KEY),
                "provider": "deepseek" if settings.LLM_DEEPSEEK_API_KEY else "openai",
                "baseUrl": "https://api.deepseek.com/v1",
                "apiKey": settings.LLM_DEEPSEEK_API_KEY or "",
                "models": {
                    "classify": "deepseek-chat",
                    "analyze": "deepseek-chat",
                    "explain": "deepseek-chat",
                },
            },
            "local": {
                "enabled": False,
                "endpoint": settings.OLLAMA_ENDPOINT,
                "models": {
                    "classify": "qwen2.5:7b",
                    "analyze": "qwen2.5:32b",
                    "explain": "qwen2.5:7b",
                },
            },
        }

        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # 问题 7 修复：用深合并替代 dict.update()
                    for key in ["remote", "local"]:
                        if key in saved and key in default_config:
                            default_config[key] = _deep_merge(
                                default_config[key], saved[key]
                            )
            except Exception as e:
                logger.warning("加载 LLM 配置文件失败: %s", e)

        return default_config

    def _init_clients(self) -> None:
        """初始化各提供商的 OpenAI 兼容客户端"""
        self._config = self._load_config_from_file()

        # 远程 API
        remote = self._config.get("remote", {})
        if remote.get("enabled") and remote.get("apiKey"):
            provider = remote.get("provider", "deepseek")
            base_url = remote.get("baseUrl", "https://api.deepseek.com/v1")
            self._clients[provider] = AsyncOpenAI(
                api_key=remote["apiKey"],
                base_url=base_url,
                timeout=120.0,
            )
            logger.info("LLM 远程提供商已初始化: %s (base_url=%s)", provider, base_url)

        # 本地 Ollama
        local = self._config.get("local", {})
        if local.get("enabled"):
            endpoint = local.get("endpoint", settings.OLLAMA_ENDPOINT)
            self._clients["ollama"] = AsyncOpenAI(
                api_key="ollama",
                base_url=endpoint + "/v1",
                timeout=300.0,
            )
            logger.info("LLM 本地模型已初始化: ollama (endpoint=%s)", endpoint)

        # 如果没有从配置文件加载到，使用默认配置
        if not self._clients:
            logger.info("使用默认 LLM 配置")
            if settings.LLM_DEEPSEEK_API_KEY:
                self._clients["deepseek"] = AsyncOpenAI(
                    api_key=settings.LLM_DEEPSEEK_API_KEY,
                    base_url="https://api.deepseek.com/v1",
                    timeout=120.0,
                )
                logger.info("LLM 提供商已初始化: deepseek (默认配置)")
            if settings.LLM_OPENAI_API_KEY:
                self._clients["openai"] = AsyncOpenAI(
                    api_key=settings.LLM_OPENAI_API_KEY,
                    base_url="https://api.openai.com/v1",
                    timeout=120.0,
                )
                logger.info("LLM 提供商已初始化: openai (默认配置)")
            if settings.OLLAMA_ENDPOINT:
                self._clients["ollama"] = AsyncOpenAI(
                    api_key="ollama",
                    base_url=settings.OLLAMA_ENDPOINT + "/v1",
                    timeout=300.0,
                )
                logger.info("LLM 本地模型已初始化: ollama (默认配置)")

    def reload_config(self) -> None:
        """重新加载配置（配置更新后调用）"""
        self._clients.clear()
        self._init_clients()
        logger.info("LLM 网关配置已重新加载，可用提供商: %s", list(self._clients.keys()))

    # ── 模型选择（问题 2 修复：优先从配置文件读取模型名） ──

    def _get_model(self, provider: str, task: str) -> str:
        """
        获取指定提供商+任务对应的模型名。

        优先级：配置文件 models 字段 > 硬编码 TASK_MODEL_FALLBACK
        """
        # 1. 从配置文件读取
        config_key = _TASK_TO_CONFIG_KEY.get(task, "analyze")

        # 远程提供商
        remote = self._config.get("remote", {})
        if provider == remote.get("provider") and remote.get("models", {}).get(config_key):
            return remote["models"][config_key]

        # 本地 Ollama
        local = self._config.get("local", {})
        if provider == "ollama" and local.get("models", {}).get(config_key):
            return local["models"][config_key]

        # 2. fallback 到硬编码映射
        fallback = _TASK_MODEL_FALLBACK.get(provider, {}).get(task, "deepseek-chat")
        logger.debug("模型 fallback: provider=%s task=%s → %s", provider, task, fallback)
        return fallback

    def _get_available_providers(self) -> list[str]:
        """返回有 client 的提供商列表，配置文件中的排在前面"""
        remote_provider = self._config.get("remote", {}).get("provider", "")
        providers: list[str] = []

        # 配置文件中启用的提供商优先
        if remote_provider and remote_provider in self._clients:
            providers.append(remote_provider)
        if "ollama" in self._clients:
            providers.append("ollama")

        # 补充其他已初始化的提供商
        for p in self._clients:
            if p not in providers:
                providers.append(p)

        return providers

    # ── LLM 调用 ──

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

    async def chat_structured(
        self,
        messages: list[dict],
        schema: type[TModel],
        task: str,
        temperature: float = 0.1,
        max_retries: int = 2,
    ) -> StructuredLLMResponse:
        """
        结构化输出：优先 Outlines（OpenAI 兼容 json_schema），
        失败则回退 chat + parse_json + Pydantic 校验。
        Worker 禁止直接 import outlines，一律走本方法。
        """
        empty = StructuredLLMResponse(content="", parsed=None, via="fallback")

        if settings.OUTLINES_ENABLED:
            outlines_result = await self._chat_via_outlines(
                messages, schema, task, temperature
            )
            if outlines_result.parsed is not None:
                return outlines_result
            logger.warning(
                "Outlines 结构化调用未成功，回退 parse_json: task=%s", task
            )

        # 回退：普通 chat + 校验（可多试一次）
        last: StructuredLLMResponse = empty
        for attempt in range(max_retries + 1):
            resp = await self.chat(
                messages,
                task=task,
                temperature=temperature if attempt == 0 else min(temperature + 0.1, 0.5),
                max_retries=0,
            )
            if not resp.content:
                last = StructuredLLMResponse(
                    content="",
                    model=resp.model,
                    provider=resp.provider,
                    tokens_used=resp.tokens_used,
                    latency_ms=resp.latency_ms,
                    parsed=None,
                    via="fallback",
                )
                continue
            parsed = self._validate_schema(resp.content, schema)
            last = StructuredLLMResponse(
                content=resp.content,
                model=resp.model,
                provider=resp.provider,
                tokens_used=resp.tokens_used,
                latency_ms=resp.latency_ms,
                parsed=parsed,
                via="fallback",
            )
            if parsed is not None:
                return last
        return last

    async def _chat_via_outlines(
        self,
        messages: list[dict],
        schema: type[TModel],
        task: str,
        temperature: float,
    ) -> StructuredLLMResponse:
        """经 Outlines + AsyncOpenAI 客户端做结构化生成"""
        try:
            import outlines
            from outlines.inputs import Chat
        except ImportError as exc:
            logger.warning("outlines 未安装，跳过结构化路径: %s", exc)
            return StructuredLLMResponse(parsed=None, via="outlines")

        providers = self._get_available_providers()
        if not providers:
            return StructuredLLMResponse(parsed=None, via="outlines")

        last_error: Exception | None = None
        for provider in providers:
            client = self._clients.get(provider)
            if not client:
                continue
            model_name = self._get_model(provider, task)
            if (provider, model_name) in self._structured_unsupported:
                logger.debug(
                    "跳过 Outlines（该模型不支持 response_format）: provider=%s model=%s",
                    provider,
                    model_name,
                )
                continue
            start = time.monotonic()
            try:
                omodel = outlines.from_openai(client, model_name)
                chat_input = Chat(messages)
                raw = await omodel(chat_input, schema, temperature=temperature)
                latency = int((time.monotonic() - start) * 1000)

                if isinstance(raw, BaseModel):
                    content = raw.model_dump_json()
                    parsed: BaseModel | None = raw
                elif isinstance(raw, str):
                    content = raw
                    parsed = self._validate_schema(raw, schema)
                else:
                    content = json.dumps(raw, ensure_ascii=False)
                    parsed = self._validate_schema(content, schema)

                if parsed is None:
                    logger.warning(
                        "Outlines 返回无法校验: provider=%s model=%s",
                        provider,
                        model_name,
                    )
                    continue

                logger.info(
                    "Outlines 结构化成功: provider=%s model=%s task=%s latency=%dms",
                    provider,
                    model_name,
                    task,
                    latency,
                )
                return StructuredLLMResponse(
                    content=content,
                    model=model_name,
                    provider=provider,
                    latency_ms=latency,
                    parsed=parsed,
                    via="outlines",
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Outlines 调用失败: provider=%s model=%s error=%s",
                    provider,
                    model_name,
                    e,
                )
                if (
                    "response_format" in str(e).lower()
                    or "unavailable now" in str(e).lower()
                ):
                    # 该模型不支持 json_schema 结构化输出，记录后跳过，避免每次调用都失败一次
                    self._structured_unsupported.add((provider, model_name))
                    logger.warning(
                        "Outlines 不支持当前模型，已记录并跳过后续调用: provider=%s model=%s",
                        provider,
                        model_name,
                    )
                continue

        if last_error:
            logger.warning("Outlines 全部提供商失败: %s", last_error)
        return StructuredLLMResponse(parsed=None, via="outlines")

    def _validate_schema(
        self, content: str, schema: type[TModel]
    ) -> TModel | None:
        """parse_json + Pydantic model_validate"""
        data = self.parse_json(content)
        if data is None:
            return None
        try:
            if isinstance(data, list):
                # 允许裸数组：若 schema 有单一 list 字段则包装
                fields = getattr(schema, "model_fields", {})
                if len(fields) == 1:
                    only = next(iter(fields))
                    return schema.model_validate({only: data})
            return schema.model_validate(data)
        except ValidationError as e:
            logger.warning("Schema 校验失败: %s", e)
            return None

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
