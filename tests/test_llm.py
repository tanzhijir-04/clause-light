"""LLM 网关测试"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.core.llm import LLMGateway, LLMResponse


class TestLLMParseJson:
    """JSON 解析测试"""

    def setup_method(self):
        """初始化 LLM 网关（不初始化客户端）"""
        self.gateway = LLMGateway()
        self.gateway._clients = {}

    def test_parse_json_direct(self):
        """测试直接解析 JSON"""
        content = '{"risk_level": "red", "severity_score": 8}'
        result = self.gateway.parse_json(content)
        assert result == {"risk_level": "red", "severity_score": 8}

    def test_parse_json_array(self):
        """测试解析 JSON 数组"""
        content = '[{"clause_number": "第一条"}, {"clause_number": "第二条"}]'
        result = self.gateway.parse_json(content)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_parse_json_with_markdown_fence(self):
        """测试解析带 markdown 代码块的 JSON"""
        content = '''这是分析结果：

```json
{"risk_level": "yellow", "severity_score": 5}
```

请参考。'''
        result = self.gateway.parse_json(content)
        assert result == {"risk_level": "yellow", "severity_score": 5}

    def test_parse_json_with_text_prefix(self):
        """测试解析带文本前缀的 JSON"""
        content = '以下是分析结果：\n{"risk_level": "green"}'
        result = self.gateway.parse_json(content)
        assert result == {"risk_level": "green"}

    def test_parse_json_invalid(self):
        """测试无效 JSON"""
        content = "这不是 JSON 格式的内容"
        result = self.gateway.parse_json(content)
        assert result is None

    def test_parse_json_empty(self):
        """测试空字符串"""
        result = self.gateway.parse_json("")
        assert result is None


class TestLLMResponse:
    """LLM 响应数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        resp = LLMResponse()
        assert resp.content == ""
        assert resp.model == ""
        assert resp.provider == ""
        assert resp.tokens_used == 0
        assert resp.latency_ms == 0

    def test_custom_values(self):
        """测试自定义值"""
        resp = LLMResponse(
            content="测试内容",
            model="deepseek-chat",
            provider="deepseek",
            tokens_used=100,
            latency_ms=500,
        )
        assert resp.content == "测试内容"
        assert resp.tokens_used == 100


class TestLLMGatewayInit:
    """LLM 网关初始化测试"""

    def test_no_clients_without_keys(self):
        """测试无 API Key 时不创建客户端"""
        empty_config = {
            "remote": {"enabled": False, "provider": "deepseek", "baseUrl": "", "apiKey": "", "models": {}},
            "local": {"enabled": False, "endpoint": "", "models": {}},
        }
        with patch("server.core.llm.settings") as mock_settings:
            mock_settings.LLM_DEEPSEEK_API_KEY = ""
            mock_settings.LLM_OPENAI_API_KEY = ""
            mock_settings.LLM_QWEN_API_KEY = ""
            mock_settings.OLLAMA_ENDPOINT = ""
            with patch.object(LLMGateway, "_load_config_from_file", return_value=empty_config):
                gateway = LLMGateway()
                assert len(gateway._clients) == 0

    def test_ollama_client_always_created(self):
        """测试 Ollama 客户端始终创建"""
        ollama_config = {
            "remote": {"enabled": False, "provider": "deepseek", "baseUrl": "", "apiKey": "", "models": {}},
            "local": {"enabled": True, "endpoint": "http://localhost:11434", "models": {}},
        }
        with patch("server.core.llm.settings") as mock_settings:
            mock_settings.LLM_DEEPSEEK_API_KEY = ""
            mock_settings.LLM_OPENAI_API_KEY = ""
            mock_settings.LLM_QWEN_API_KEY = ""
            mock_settings.OLLAMA_ENDPOINT = "http://localhost:11434"
            with patch.object(LLMGateway, "_load_config_from_file", return_value=ollama_config):
                gateway = LLMGateway()
                assert "ollama" in gateway._clients

    def test_processing_plan_distinguishes_remote_and_local_without_network(self):
        gateway = LLMGateway.__new__(LLMGateway)
        gateway._clients = {}
        gateway._structured_unsupported = set()
        gateway._config = {
            "remote": {"enabled": True, "provider": "deepseek", "models": {"analyze": "deepseek-chat"}},
            "local": {"enabled": True, "models": {"analyze": "qwen2.5:7b"}},
        }
        remote = gateway.get_processing_plan()
        assert remote.processing_mode == "remote"
        assert remote.provider == "deepseek"

        gateway._config["remote"]["enabled"] = False
        local = gateway.get_processing_plan()
        assert local.processing_mode == "local"
        assert local.provider == "ollama"


class TestLLMGatewayChat:
    """LLM 网关 chat 方法测试"""

    async def test_chat_no_providers(self):
        """测试无可用提供商时返回空响应"""
        gateway = LLMGateway()
        gateway._clients = {}
        result = await gateway.chat(
            messages=[{"role": "user", "content": "测试"}],
            task="analysis",
        )
        assert result.content == ""
        assert result.provider == ""

    async def test_chat_success(self):
        """测试成功调用"""
        gateway = LLMGateway()

        # Mock OpenAI 客户端
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="测试回复"))]
        mock_response.usage = MagicMock(total_tokens=50)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        gateway._clients = {"deepseek": mock_client}
        gateway._get_available_providers = lambda: ["deepseek"]
        gateway._get_model = lambda provider, task: "deepseek-chat"

        result = await gateway.chat(
            messages=[{"role": "user", "content": "测试"}],
            task="analysis",
        )
        assert result.content == "测试回复"
        assert result.provider == "deepseek"
        assert result.tokens_used == 50

    async def test_chat_with_retry(self):
        """测试失败重试"""
        gateway = LLMGateway()

        mock_client = AsyncMock()
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("API 错误")
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content="重试成功"))],
                usage=MagicMock(total_tokens=30),
            )

        mock_client.chat.completions.create = side_effect
        gateway._clients = {"deepseek": mock_client}
        gateway._get_available_providers = lambda: ["deepseek"]
        gateway._get_model = lambda provider, task: "deepseek-chat"

        result = await gateway.chat(
            messages=[{"role": "user", "content": "测试"}],
            task="analysis",
            max_retries=2,
        )
        assert result.content == "重试成功"
        assert call_count == 3
