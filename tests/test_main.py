"""主入口和配置测试"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.config import settings


class TestConfig:
    """配置测试"""

    def test_default_values(self):
        """测试默认配置值"""
        assert settings.PORT == 8080
        assert settings.MAX_UPLOAD_SIZE == 20 * 1024 * 1024
        assert settings.OCR_USE_GPU is False

    def test_database_url(self):
        """测试数据库 URL"""
        assert "sqlite" in settings.DATABASE_URL


class TestRootRedirect:
    """根路径重定向测试"""

    async def test_root_redirects(self, client):
        """测试根路径重定向到管理面板"""
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/admin" in response.headers["location"]


class TestDevicesEndpoint:
    """设备列表接口测试"""

    async def test_list_devices(self, client):
        """测试获取设备列表"""
        response = await client.get("/api/devices")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "iPhone 15 Pro"


class TestLLMSettings:
    """LLM 配置接口测试"""

    async def test_get_llm_settings(self, client):
        """测试获取 LLM 配置"""
        response = await client.get("/api/settings/llm")
        assert response.status_code == 200
        data = response.json()
        assert "remote" in data
        assert "local" in data
        assert data["local"]["endpoint"] == settings.OLLAMA_ENDPOINT

    async def test_update_llm_settings(self, client):
        """测试更新 LLM 配置"""
        response = await client.put(
            "/api/settings/llm",
            json={"remote": {"enabled": True}},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
