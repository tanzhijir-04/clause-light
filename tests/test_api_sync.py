"""同步 API 接口测试"""

from __future__ import annotations

import pytest

from server.models.database import SyncLog


class TestSyncConfig:
    """同步配置接口测试"""

    async def test_get_config(self, client):
        """测试获取同步配置"""
        response = await client.get("/api/sync/config")
        assert response.status_code == 200
        data = response.json()
        assert "webdav" in data
        assert "git" in data
        assert "s3" in data
        assert data["webdav"]["enabled"] is False

    async def test_update_config(self, client):
        """测试更新同步配置"""
        response = await client.put(
            "/api/sync/config",
            json={
                "webdav": {"enabled": True, "url": "https://example.com"},
                "git": {"enabled": False},
                "s3": {"enabled": False},
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestSyncPush:
    """手动上传接口测试"""

    async def test_push_success(self, client):
        """测试成功上传"""
        response = await client.post("/api/sync/push")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "上传完成" in data["message"]


class TestSyncPull:
    """手动下载接口测试"""

    async def test_pull_success(self, client):
        """测试成功下载"""
        response = await client.post("/api/sync/pull")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "下载完成" in data["message"]


class TestSyncLog:
    """同步历史接口测试"""

    async def test_get_log_empty(self, client):
        """测试空历史"""
        response = await client.get("/api/sync/log")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_log_with_data(self, client, db_session):
        """测试有数据的历史"""
        logs = [
            SyncLog(
                id=f"sync_log_{i}",
                sync_type="webdav",
                direction="push",
                status="success",
                details=f"同步 {i}",
            )
            for i in range(3)
        ]
        db_session.add_all(logs)
        await db_session.commit()

        response = await client.get("/api/sync/log")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
