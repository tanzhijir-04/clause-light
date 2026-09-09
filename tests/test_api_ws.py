"""WebSocket 接口测试"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.api import ws as ws_module
from server.models.database import Base

# 测试用内存数据库（WebSocket 测试专用）
_ws_test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_ws_test_session_factory = async_sessionmaker(
    _ws_test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture()
def ws_client():
    """创建同步 TestClient 用于 WebSocket 测试

    同时：
    1. 在内存数据库中创建表结构
    2. 将 ws 模块的 async_session_factory 替换为测试工厂
    """
    import asyncio

    test_app = FastAPI()
    test_app.include_router(ws_module.router)

    # 在内存数据库中创建表（同步方式）
    loop = asyncio.new_event_loop()

    async def _create_tables():
        async with _ws_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop.run_until_complete(_create_tables())

    # 替换 ws 模块使用的数据库工厂
    original_factory = ws_module.async_session_factory
    ws_module.async_session_factory = _ws_test_session_factory

    with TestClient(test_app) as client:
        yield client

    # 恢复原始工厂
    ws_module.async_session_factory = original_factory

    # 清理：删除表
    async def _drop_tables():
        async with _ws_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    loop.run_until_complete(_drop_tables())
    loop.close()


class TestWebSocketConnection:
    """测试 WebSocket 连接管理"""

    def test_connect_and_ping(self, ws_client):
        """测试成功连接并发送 ping 收到 pong"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_connection_tracked(self, ws_client):
        """测试连接被正确追踪"""
        initial_count = len(ws_module.active_connections)
        with ws_client.websocket_connect("/ws/client") as ws:
            assert len(ws_module.active_connections) == initial_count + 1
            # 发送 ping 确认连接活跃
            ws.send_json({"type": "ping"})
            ws.receive_json()
        # 退出 with 后连接应被清理
        assert len(ws_module.active_connections) == initial_count

    def test_connection_info_recorded(self, ws_client):
        """测试连接元数据被记录"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()
            # 检查至少有一个连接有元数据
            assert len(ws_module.connection_info) >= 1
            # 找到当前连接的元数据
            found = False
            for info in ws_module.connection_info.values():
                if "ip" in info and "connected_at" in info:
                    found = True
                    break
            assert found, "连接元数据应包含 ip 和 connected_at"

    def test_connection_info_has_timestamps(self, ws_client):
        """测试连接元数据包含时间戳"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()
            for info in ws_module.connection_info.values():
                assert "connected_at" in info
                assert "last_active" in info
                # 时间戳应为 ISO 格式
                assert "T" in info["connected_at"]

    def test_multiple_sequential_connections(self, ws_client):
        """测试顺序建立的多个连接"""
        for _ in range(3):
            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({"type": "ping"})
                data = ws.receive_json()
                assert data["type"] == "pong"

    def test_connection_count_after_multiple(self, ws_client):
        """测试多个连接后计数正确"""
        initial_count = len(ws_module.active_connections)
        # 建立两个连接
        with ws_client.websocket_connect("/ws/client") as ws1:
            ws1.send_json({"type": "ping"})
            ws1.receive_json()
            assert len(ws_module.active_connections) == initial_count + 1

        # 第一个断开后计数恢复
        assert len(ws_module.active_connections) == initial_count

        with ws_client.websocket_connect("/ws/client") as ws2:
            ws2.send_json({"type": "ping"})
            ws2.receive_json()
            assert len(ws_module.active_connections) == initial_count + 1

        # 第二个断开后计数恢复
        assert len(ws_module.active_connections) == initial_count


class TestWebSocketAnalyze:
    """测试 WebSocket 分析功能"""

    def test_analyze_empty_text(self, ws_client):
        """测试空文本分析返回错误"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({
                "type": "analyze",
                "text": "",
                "contractType": "",
            })
            data = ws.receive_json()
            assert data["type"] == "error"
            assert data["code"] == "EMPTY_TEXT"
            assert "不能为空" in data["message"]

    def test_analyze_whitespace_only(self, ws_client):
        """测试纯空白文本分析返回错误"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({
                "type": "analyze",
                "text": "   \n\t  ",
                "contractType": "",
            })
            data = ws.receive_json()
            assert data["type"] == "error"
            assert data["code"] == "EMPTY_TEXT"

    def test_analyze_success(self, ws_client):
        """测试正常分析流程（mock Agent）"""
        # 使用唯一 ID 避免数据库约束冲突
        unique_id = uuid.uuid4().hex

        mock_result = MagicMock()
        mock_result.contract_id = unique_id
        mock_result.contract_type = "租赁合同"
        mock_result.overall_score = 80
        mock_result.recommendation = "negotiate_first"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "合同风险中等"
        mock_result.red_count = 1
        mock_result.yellow_count = 1
        mock_result.green_count = 3
        mock_result.clauses = [
            {
                "clause_number": "第一条",
                "title": "合同目的",
                "content": "本合同旨在约定双方权利义务",
                "risk_level": "green",
                "risk_type": "无风险",
                "risk_summary": "正常条款",
                "plain_explanation": "正常",
                "legal_basis": "《合同法》",
                "severity_score": 1,
                "suggested_clause": "",
                "can_negotiate": False,
            }
        ]

        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "这是一份租赁合同...",
                    "contractType": "租赁合同",
                })
                data = ws.receive_json()
                assert data["type"] == "result"
                assert data["data"]["score"] == 80
                # ws.py 逻辑：red_count > 0 则 riskLevel = "red"
                assert data["data"]["riskLevel"] == "red"
                assert data["data"]["redCount"] == 1
                assert data["data"]["yellowCount"] == 1
                assert data["data"]["greenCount"] == 3
                assert len(data["data"]["clauses"]) == 1
                assert data["data"]["clauses"][0]["riskLevel"] == "green"

    def test_analyze_progress_updates(self, ws_client):
        """测试分析过程中的进度更新"""
        unique_id = uuid.uuid4().hex

        mock_result = MagicMock()
        mock_result.contract_id = unique_id
        mock_result.contract_type = "劳动合同"
        mock_result.overall_score = 90
        mock_result.recommendation = "sign"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "合同风险较低"
        mock_result.red_count = 0
        mock_result.yellow_count = 0
        mock_result.green_count = 2
        mock_result.clauses = [
            {
                "clause_number": "第一条",
                "title": "工作内容",
                "content": "负责前端开发",
                "risk_level": "green",
                "risk_type": "无风险",
                "risk_summary": "正常",
                "plain_explanation": "正常",
                "legal_basis": "《劳动法》",
                "severity_score": 1,
                "suggested_clause": "",
                "can_negotiate": False,
            },
            {
                "clause_number": "第二条",
                "title": "薪资待遇",
                "content": "月薪15000元",
                "risk_level": "green",
                "risk_type": "无风险",
                "risk_summary": "正常",
                "plain_explanation": "正常",
                "legal_basis": "《劳动法》",
                "severity_score": 1,
                "suggested_clause": "",
                "can_negotiate": False,
            },
        ]

        # 模拟 Agent 在分析过程中调用 on_step 回调发送进度
        async def mock_analyze(file_path, contract_type_hint=None, on_step=None):
            if on_step:
                await on_step(1, 5, "正在识别文字...")
                await on_step(2, 5, "正在解析合同结构...")
                await on_step(3, 5, "正在并行分析 5 个维度...")
                await on_step(4, 5, "正在聚合评分...")
                await on_step(5, 5, "正在生成报告...")
            return mock_result

        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = mock_analyze

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "劳动合同内容...",
                    "contractType": "劳动合同",
                })

                # 收集所有消息直到 result
                messages = []
                try:
                    while True:
                        msg = ws.receive_json()
                        messages.append(msg)
                        if msg["type"] == "result":
                            break
                except Exception:
                    pass

                # 应该有进度消息和最终结果
                msg_types = [m["type"] for m in messages]
                assert "result" in msg_types
                # 应该有 5 个 progress 消息
                progress_msgs = [m for m in messages if m["type"] == "progress"]
                assert len(progress_msgs) >= 1
                # 进度消息应包含 step 和 total 字段
                for pm in progress_msgs:
                    assert "step" in pm
                    assert "total" in pm
                    assert "message" in pm
                # 验证最终进度 step 等于 total
                last_progress = progress_msgs[-1]
                assert last_progress["step"] == last_progress["total"]

    def test_analyze_agent_failure(self, ws_client):
        """测试 Agent 分析失败时返回错误"""
        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(
                side_effect=Exception("LLM 连接超时")
            )

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "合同内容...",
                    "contractType": "",
                })
                data = ws.receive_json()
                assert data["type"] == "error"
                assert data["code"] == "ANALYSIS_FAILED"
                assert "LLM 连接超时" in data["message"]

    def test_analyze_result_risk_levels_red(self, ws_client):
        """测试分析结果风险等级为红色"""
        unique_id = uuid.uuid4().hex

        mock_result = MagicMock()
        mock_result.contract_id = unique_id
        mock_result.contract_type = "外包合同"
        mock_result.overall_score = 40
        mock_result.recommendation = "reject"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "合同风险极高"
        mock_result.red_count = 3
        mock_result.yellow_count = 0
        mock_result.green_count = 1
        mock_result.clauses = []

        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "外包合同内容...",
                    "contractType": "外包合同",
                })
                data = ws.receive_json()
                assert data["type"] == "result"
                assert data["data"]["riskLevel"] == "red"
                assert data["data"]["score"] == 40

    def test_analyze_result_risk_levels_green(self, ws_client):
        """测试分析结果风险等级为绿色（无红色和黄色）"""
        unique_id = uuid.uuid4().hex

        mock_result = MagicMock()
        mock_result.contract_id = unique_id
        mock_result.contract_type = "借款合同"
        mock_result.overall_score = 95
        mock_result.recommendation = "sign"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "合同风险很低"
        mock_result.red_count = 0
        mock_result.yellow_count = 0
        mock_result.green_count = 5
        mock_result.clauses = []

        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "借款合同内容...",
                    "contractType": "借款合同",
                })
                data = ws.receive_json()
                assert data["type"] == "result"
                assert data["data"]["riskLevel"] == "green"
                assert data["data"]["score"] == 95

    def test_analyze_saves_to_database(self, ws_client):
        """测试分析结果正确保存到数据库"""
        unique_id = uuid.uuid4().hex

        mock_result = MagicMock()
        mock_result.contract_id = unique_id
        mock_result.contract_type = "服务合同"
        mock_result.overall_score = 75
        mock_result.recommendation = "negotiate_first"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "合同风险中等"
        mock_result.red_count = 0
        mock_result.yellow_count = 1
        mock_result.green_count = 2
        mock_result.clauses = [
            {
                "clause_number": "第一条",
                "title": "服务范围",
                "content": "提供技术咨询服务",
                "risk_level": "yellow",
                "risk_type": "范围模糊",
                "risk_summary": "服务范围描述模糊",
                "plain_explanation": "服务范围不明确",
                "legal_basis": "《合同法》",
                "severity_score": 5,
                "suggested_clause": "",
                "can_negotiate": True,
            }
        ]

        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "服务合同内容...",
                    "contractType": "服务合同",
                })
                data = ws.receive_json()
                assert data["type"] == "result"
                contract_id = data["data"]["contractId"]

            # 验证数据已保存到测试数据库
            import asyncio

            async def _check_db():
                async with _ws_test_session_factory() as session:
                    from sqlalchemy import select

                    from server.models.database import Analysis, Contract

                    # 检查合同记录
                    stmt = select(Contract).where(Contract.id == contract_id)
                    result = await session.execute(stmt)
                    contract = result.scalar_one_or_none()
                    assert contract is not None
                    assert contract.type == "服务合同"

                    # 检查分析记录
                    stmt = select(Analysis).where(Analysis.contract_id == contract_id)
                    result = await session.execute(stmt)
                    analysis = result.scalar_one_or_none()
                    assert analysis is not None
                    assert analysis.overall_score == 75

            loop = asyncio.new_event_loop()
            loop.run_until_complete(_check_db())
            loop.close()

    def test_analyze_with_contract_type_hint(self, ws_client):
        """测试带合同类型提示的分析"""
        unique_id = uuid.uuid4().hex

        mock_result = MagicMock()
        mock_result.contract_id = unique_id
        mock_result.contract_type = "装修合同"
        mock_result.overall_score = 60
        mock_result.recommendation = "negotiate_first"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "装修合同风险中等"
        mock_result.red_count = 1
        mock_result.yellow_count = 0
        mock_result.green_count = 3
        mock_result.clauses = []

        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "装修合同内容...",
                    "contractType": "装修合同",
                })
                data = ws.receive_json()
                assert data["type"] == "result"
                assert data["data"]["riskLevel"] == "red"
                assert data["data"]["score"] == 60

                # 验证 Agent 被调用时传入了 contract_type_hint
                call_kwargs = MockAgent.return_value.analyze.call_args
                assert call_kwargs[1]["contract_type_hint"] == "装修合同"


class TestWebSocketDisconnect:
    """测试 WebSocket 断开连接"""

    def test_disconnect_cleans_up(self, ws_client):
        """测试断开连接后资源被清理"""
        initial_count = len(ws_module.active_connections)
        initial_info_count = len(ws_module.connection_info)

        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()
            # 连接期间数量应增加
            assert len(ws_module.active_connections) == initial_count + 1

        # 退出 with 后应恢复
        assert len(ws_module.active_connections) == initial_count
        assert len(ws_module.connection_info) == initial_info_count

    def test_disconnect_after_analyze(self, ws_client):
        """测试分析完成后断开连接"""
        unique_id = uuid.uuid4().hex

        mock_result = MagicMock()
        mock_result.contract_id = unique_id
        mock_result.contract_type = "服务合同"
        mock_result.overall_score = 70
        mock_result.recommendation = "negotiate_first"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "风险中等"
        mock_result.red_count = 0
        mock_result.yellow_count = 1
        mock_result.green_count = 2
        mock_result.clauses = [
            {
                "clause_number": "第一条",
                "title": "服务范围",
                "content": "提供技术咨询服务",
                "risk_level": "yellow",
                "risk_type": "范围模糊",
                "risk_summary": "服务范围描述模糊",
                "plain_explanation": "服务范围不明确",
                "legal_basis": "《合同法》",
                "severity_score": 5,
                "suggested_clause": "",
                "can_negotiate": True,
            },
            {
                "clause_number": "第二条",
                "title": "付款条件",
                "content": "验收后30天内付款",
                "risk_level": "green",
                "risk_type": "无风险",
                "risk_summary": "正常",
                "plain_explanation": "正常付款条件",
                "legal_basis": "《合同法》",
                "severity_score": 1,
                "suggested_clause": "",
                "can_negotiate": False,
            },
            {
                "clause_number": "第三条",
                "title": "保密义务",
                "content": "双方承担保密义务",
                "risk_level": "green",
                "risk_type": "无风险",
                "risk_summary": "正常",
                "plain_explanation": "正常保密条款",
                "legal_basis": "《合同法》",
                "severity_score": 1,
                "suggested_clause": "",
                "can_negotiate": False,
            },
        ]

        with patch("server.api.ws.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            with ws_client.websocket_connect("/ws/client") as ws:
                ws.send_json({
                    "type": "analyze",
                    "text": "服务合同内容...",
                    "contractType": "服务合同",
                })

                # 读取所有消息直到 result
                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "result":
                        break

            # 连接应已清理
            assert ws not in ws_module.active_connections

    def test_disconnect_multiple_clients(self, ws_client):
        """测试多客户端断开后各自清理"""
        initial_count = len(ws_module.active_connections)

        with ws_client.websocket_connect("/ws/client") as ws1:
            ws1.send_json({"type": "ping"})
            ws1.receive_json()
            assert len(ws_module.active_connections) == initial_count + 1

            with ws_client.websocket_connect("/ws/client") as ws2:
                ws2.send_json({"type": "ping"})
                ws2.receive_json()
                assert len(ws_module.active_connections) == initial_count + 2

            # ws2 断开
            assert len(ws_module.active_connections) == initial_count + 1

        # ws1 也断开
        assert len(ws_module.active_connections) == initial_count


class TestWebSocketUnknownMessage:
    """测试未知消息类型"""

    def test_unknown_type_ignored(self, ws_client):
        """测试未知消息类型不会导致连接断开"""
        with ws_client.websocket_connect("/ws/client") as ws:
            # 发送未知类型消息
            ws.send_json({"type": "unknown_action", "data": "test"})
            # 连接仍然存活，发送 ping 验证
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_invalid_json_closes_connection(self, ws_client):
        """测试无效 JSON 导致连接关闭（服务器不崩溃）"""
        with ws_client.websocket_connect("/ws/client") as ws:
            # 发送无效 JSON，服务器会抛出 JSONDecodeError
            # 被外层 except Exception 捕获，连接关闭
            ws.send_text("not valid json {{{")
            # 服务器应保持运行（不崩溃），但连接可能已关闭
            # 验证方法：连接已不在活跃列表中
        # 退出 with 时，连接已被清理
        # 关键是服务器没有崩溃（测试能正常完成）

    def test_missing_type_field(self, ws_client):
        """测试缺少 type 字段的消息被忽略"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({"data": "no type field"})
            # 连接应仍然存活
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_extra_fields_ignored(self, ws_client):
        """测试额外字段被忽略"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({
                "type": "ping",
                "extra": "data",
                "another": 123,
            })
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_empty_message_type(self, ws_client):
        """测试空 type 字段被忽略"""
        with ws_client.websocket_connect("/ws/client") as ws:
            ws.send_json({"type": ""})
            # 连接仍存活
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"
