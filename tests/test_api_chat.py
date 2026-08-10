"""合同多轮追问 Chat API 测试"""

from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from server.models.database import Analysis, Contract, MemoryEvent, get_db


class FakeLLM:
    """返回固定追问回复的假 LLM"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def chat(self, messages, task="analysis", **kwargs):
        self.calls.append({"messages": messages, "task": task, **kwargs})

        class R:
            content = "这是关于违约金条款的通俗解释。"

        return R()


@pytest_asyncio.fixture
async def chat_client() -> AsyncGenerator[AsyncClient, None]:
    """仅挂载 chat 路由，避免 server.main 可选依赖"""
    from fastapi import FastAPI

    from server.api.chat import router
    from tests.conftest import override_get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_contract(db_session, *, with_analysis: bool = True) -> str:
    """写入测试合同（及可选分析）"""
    cid = "chat-contract-1"
    db_session.add(
        Contract(
            id=cid,
            title="测试租赁合同",
            type="租赁合同",
            ocr_text="甲方出租房屋给乙方。" * 100,
        )
    )
    if with_analysis:
        db_session.add(
            Analysis(
                id="analysis-1",
                contract_id=cid,
                overall_score=65,
                summary="存在违约金偏高风险",
                recommendation="negotiate_first",
            )
        )
    await db_session.commit()
    return cid


@pytest.mark.asyncio
async def test_chat_returns_reply_and_session(chat_client, db_session):
    """首次追问：创建 session，返回 reply + session_id，写入 L0 事件"""
    cid = await _seed_contract(db_session)
    fake = FakeLLM()

    with patch("server.api.chat.get_llm_gateway", return_value=fake):
        r = await chat_client.post(
            f"/api/contracts/{cid}/chat",
            json={"message": "违约金合理吗？", "session_id": None},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["reply"] == "这是关于违约金条款的通俗解释。"
    assert data["session_id"]
    assert fake.calls and fake.calls[0]["task"] == "explanation"

    # 合同摘要与分析摘要应进入 prompt
    prompt_text = " ".join(
        m.get("content", "") for m in fake.calls[0]["messages"]
    )
    assert "测试租赁合同" in prompt_text
    assert "存在违约金偏高风险" in prompt_text
    assert "甲方出租房屋" in prompt_text

    events = (
        await db_session.execute(
            select(MemoryEvent).where(MemoryEvent.session_id == data["session_id"])
        )
    ).scalars().all()
    types = {e.event_type for e in events}
    assert "user_message" in types
    assert "assistant_message" in types


@pytest.mark.asyncio
async def test_chat_reuses_session_id(chat_client, db_session):
    """传入已有 session_id 时应复用，不新建"""
    cid = await _seed_contract(db_session)
    fake = FakeLLM()

    with patch("server.api.chat.get_llm_gateway", return_value=fake):
        first = await chat_client.post(
            f"/api/contracts/{cid}/chat",
            json={"message": "第一问", "session_id": None},
        )
        sid = first.json()["session_id"]
        second = await chat_client.post(
            f"/api/contracts/{cid}/chat",
            json={"message": "第二问", "session_id": sid},
        )

    assert second.status_code == 200
    assert second.json()["session_id"] == sid


@pytest.mark.asyncio
async def test_chat_contract_not_found(chat_client):
    fake = FakeLLM()
    with patch("server.api.chat.get_llm_gateway", return_value=fake):
        r = await chat_client.post(
            "/api/contracts/missing/chat",
            json={"message": "你好", "session_id": None},
        )
    assert r.status_code == 404
