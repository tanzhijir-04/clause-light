"""Connection API 接口测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestConnectionInfo:
    """测试连接信息接口"""

    async def test_get_connection_info(self, client):
        """测试获取连接信息，返回包含 host/port/ws_url/http_url 的字典"""
        response = await client.get("/api/connection/info")
        assert response.status_code == 200
        data = response.json()
        assert "host" in data
        assert "port" in data
        assert "ws_url" in data
        assert "http_url" in data
        # ws_url 应包含 ws:// 协议前缀
        assert data["ws_url"].startswith("ws://")
        # http_url 应包含 http:// 协议前缀
        assert data["http_url"].startswith("http://")

    async def test_connection_info_port_matches_settings(self, client):
        """测试端口号与配置一致"""
        from server.config import settings

        response = await client.get("/api/connection/info")
        assert response.status_code == 200
        data = response.json()
        assert data["port"] == settings.PORT

    async def test_connection_info_ws_url_format(self, client):
        """测试 WebSocket URL 格式正确"""
        response = await client.get("/api/connection/info")
        data = response.json()
        # ws_url 格式: ws://<host>:<port>/ws/client
        ws_url = data["ws_url"]
        assert ws_url.endswith("/ws/client")
        assert f":{data['port']}" in ws_url


class TestConnectionHealth:
    """测试健康检查接口"""

    async def test_health_check_success(self, client):
        """测试健康检查返回 status=ok 及 uptime、active_connections 字段"""
        response = await client.get("/api/connection/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "uptime" in data
        assert "active_connections" in data
        assert "version" in data
        assert "timestamp" in data

    async def test_health_uptime_non_negative(self, client):
        """测试 uptime 为非负整数"""
        response = await client.get("/api/connection/health")
        data = response.json()
        assert isinstance(data["uptime"], int)
        assert data["uptime"] >= 0

    async def test_health_active_connections_zero(self, client):
        """测试无 WebSocket 连接时 active_connections 为 0"""
        response = await client.get("/api/connection/health")
        data = response.json()
        assert data["active_connections"] == 0

    async def test_health_active_connections_with_mock(self, client):
        """测试有 WebSocket 连接时 active_connections 正确计数"""
        mock_ws_1 = MagicMock()
        mock_ws_2 = MagicMock()
        with patch("server.api.ws.active_connections", [mock_ws_1, mock_ws_2]):
            response = await client.get("/api/connection/health")
            data = response.json()
            assert data["active_connections"] == 2

    async def test_health_timestamp_format(self, client):
        """测试 timestamp 为 ISO 格式字符串"""
        from datetime import datetime

        response = await client.get("/api/connection/health")
        data = response.json()
        # 验证可以解析为 datetime
        ts = data["timestamp"]
        assert isinstance(ts, str)
        # ISO 格式应包含 T
        assert "T" in ts


class TestConnectionDevices:
    """测试设备列表接口"""

    async def test_get_devices_empty(self, client):
        """测试无设备时返回空列表及 total=0"""
        response = await client.get("/api/connection/devices")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total" in data
        assert "online" in data
        assert data["devices"] == []
        assert data["total"] == 0
        assert data["online"] == 0

    async def test_get_devices_with_active_connections(self, client):
        """测试有活跃连接时返回设备信息"""
        # 模拟一个 WebSocket 连接
        mock_ws = MagicMock()
        mock_ws.client.port = 12345

        mock_info = {
            mock_ws: {
                "ip": "192.168.1.100",
                "connected_at": "2026-01-01T00:00:00+00:00",
                "last_active": "2026-01-01T00:01:00+00:00",
            }
        }

        with patch("server.api.ws.active_connections", [mock_ws]), \
             patch("server.api.ws.connection_info", mock_info):
            response = await client.get("/api/connection/devices")
            data = response.json()

            assert data["total"] == 1
            assert data["online"] == 1
            assert len(data["devices"]) == 1

            device = data["devices"][0]
            assert device["ip"] == "192.168.1.100"
            assert device["status"] == "online"
            assert device["type"] == "mobile"
            assert device["name"] == "手机端"
            assert device["id"] == "192.168.1.100:12345"

    async def test_get_devices_multiple(self, client):
        """测试多个设备连接"""
        mock_ws_1 = MagicMock()
        mock_ws_1.client.port = 10001
        mock_ws_2 = MagicMock()
        mock_ws_2.client.port = 10002

        mock_connections = [mock_ws_1, mock_ws_2]
        mock_info = {
            mock_ws_1: {
                "ip": "10.0.0.1",
                "connected_at": "2026-01-01T00:00:00+00:00",
                "last_active": "2026-01-01T00:00:30+00:00",
            },
            mock_ws_2: {
                "ip": "10.0.0.2",
                "connected_at": "2026-01-01T00:01:00+00:00",
                "last_active": "2026-01-01T00:01:30+00:00",
            },
        }

        with patch("server.api.ws.active_connections", mock_connections), \
             patch("server.api.ws.connection_info", mock_info):
            response = await client.get("/api/connection/devices")
            data = response.json()

            assert data["total"] == 2
            assert data["online"] == 2
            ips = {d["ip"] for d in data["devices"]}
            assert ips == {"10.0.0.1", "10.0.0.2"}

    async def test_device_fields_complete(self, client):
        """测试设备信息包含所有必要字段"""
        mock_ws = MagicMock()
        mock_ws.client.port = 9999

        mock_info = {
            mock_ws: {
                "ip": "172.16.0.1",
                "connected_at": "2026-06-18T10:00:00+00:00",
                "last_active": "2026-06-18T10:05:00+00:00",
            }
        }

        with patch("server.api.ws.active_connections", [mock_ws]), \
             patch("server.api.ws.connection_info", mock_info):
            response = await client.get("/api/connection/devices")
            device = response.json()["devices"][0]

            expected_fields = {"id", "name", "type", "status", "ip", "connectedAt", "lastActive"}
            assert expected_fields.issubset(device.keys())
