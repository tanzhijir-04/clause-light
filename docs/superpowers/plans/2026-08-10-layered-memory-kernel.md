# Layered Memory Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本地 SQLite 上实现 L0–L3 分层记忆的写入、预算化召回与 API，使合同审查能跨会话继承偏好与事实。

**Architecture:** 新增 `server/core/memory/` Memory Kernel；表结构扩展于 `server/models/database.py`；召回复用 `server/core/embedding.py` 并在失败时关键词降级；`NoopTeamMemoryAdapter` 预留团队同步接口。不改动 Agent Pipeline 主路径（由 Phase C 接入）。

**Tech Stack:** Python ≥3.10, FastAPI, SQLAlchemy 2.0 async, SQLite, pytest, 现有 sentence-transformers embedding

**Spec:** `docs/superpowers/specs/2026-08-10-self-evolving-memory-design.md`  
**Agent 工作流:** 根目录 `AGENTS.md`（探索→澄清→计划→实现→验证→总结）

## Global Constraints

- Python >= 3.10；后端仅 FastAPI + SQLAlchemy + SQLite；LLM 经 `server/core/llm.py`
- 前端桌面端仅纯 HTML/CSS/JS；不引入 React/Vue
- 日志不打印完整合同正文或 API Key
- 提交信息格式：`:emoji: ai-feat(类型) 简短说明`（见用户 gitmoji 规范）；**默认不 push**
- 本计划**明确要求**新增数据库表（覆盖 AGENT.md 表结构限制）
- 不接入 TencentDB 实服务；只实现 Noop 适配器
- 资产表预留 `owner_user_id` / `visibility` / `acl_json`（一期默认 local/private）
- LightRAG / Outlines **不在本 Phase 引入**（见规格 Phase A′/E）

## File Structure

| Path | Responsibility |
|------|----------------|
| `server/models/database.py` | 新增 memory_* 表模型 |
| `server/core/memory/__init__.py` | 导出 MemoryKernel |
| `server/core/memory/models.py` | dataclass：MemoryHit、RetrieveBudget、SessionInfo |
| `server/core/memory/store.py` | L0–L3 持久化 CRUD |
| `server/core/memory/retrieve.py` | 分层召回 + RRF + 字符预算 |
| `server/core/memory/kernel.py` | 门面：start_session / append_event / upsert_atom / retrieve |
| `server/core/memory/adapters/base.py` | TeamMemoryAdapter Protocol |
| `server/core/memory/adapters/noop.py` | Noop 实现 |
| `server/api/memory.py` | REST API |
| `server/main.py` | 注册 router |
| `server/config.py` | 召回预算与阈值配置 |
| `tests/test_memory_store.py` | 存储测试 |
| `tests/test_memory_retrieve.py` | 召回预算测试 |
| `tests/test_api_memory.py` | API 测试 |

---

### Task 1: Memory 配置与 dataclass

**Files:**
- Create: `server/core/memory/models.py`
- Modify: `server/config.py`
- Test: `tests/test_memory_models.py`

**Interfaces:**
- Produces: `RetrieveBudget`, `MemoryHit`, `LayerName`；`settings.MEMORY_RETRIEVE_CHAR_BUDGET` 等

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_models.py
from server.core.memory.models import RetrieveBudget, MemoryHit
from server.config import settings

def test_default_budget_values():
    b = RetrieveBudget.default()
    assert b.max_chars == 3000
    assert b.max_l1 == 8
    assert b.max_l2 == 2
    assert b.max_l3 == 3

def test_memory_hit_fields():
    hit = MemoryHit(layer="l1", id="a1", text="用户是乙方", score=0.9)
    assert hit.layer == "l1"
    assert hit.chars() == len("用户是乙方")

def test_settings_memory_budget():
    assert settings.MEMORY_RETRIEVE_CHAR_BUDGET == 3000
    assert settings.MEMORY_AUTO_ACTIVATE_THRESHOLD == 0.75
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_models.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: Implement models + settings**

```python
# server/core/memory/models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

LayerName = Literal["l0", "l1", "l2", "l3"]

@dataclass
class RetrieveBudget:
    max_chars: int = 3000
    max_l1: int = 8
    max_l2: int = 2
    max_l3: int = 3

    @classmethod
    def default(cls) -> "RetrieveBudget":
        from server.config import settings
        return cls(
            max_chars=settings.MEMORY_RETRIEVE_CHAR_BUDGET,
            max_l1=settings.MEMORY_MAX_L1,
            max_l2=settings.MEMORY_MAX_L2,
            max_l3=settings.MEMORY_MAX_L3,
        )

@dataclass
class MemoryHit:
    layer: LayerName
    id: str
    text: str
    score: float
    metadata: dict | None = None

    def chars(self) -> int:
        return len(self.text or "")
```

在 `server/config.py` 的 Settings 中增加：

```python
MEMORY_RETRIEVE_CHAR_BUDGET: int = 3000
MEMORY_MAX_L1: int = 8
MEMORY_MAX_L2: int = 2
MEMORY_MAX_L3: int = 3
MEMORY_RETRIEVE_TIMEOUT_SEC: float = 3.0
MEMORY_AUTO_ACTIVATE_THRESHOLD: float = 0.75
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/core/memory/models.py server/config.py tests/test_memory_models.py
git commit -m "$(cat <<'EOF'
:building_construction: ai-feat(新增) 分层记忆配置与命中模型

EOF
)"
```

（Windows PowerShell 可用：`git commit -m ":building_construction: ai-feat(新增) 分层记忆配置与命中模型"`）

---

### Task 2: 数据库表模型

**Files:**
- Modify: `server/models/database.py`
- Test: `tests/test_memory_db_models.py`

**Interfaces:**
- Produces: `MemorySession`, `MemoryEvent`, `MemoryAtom`, `MemoryScenario`, `MemoryPersona`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_db_models.py
import pytest
from server.models.database import (
    MemorySession, MemoryEvent, MemoryAtom, MemoryScenario, MemoryPersona,
)

@pytest.mark.asyncio
async def test_create_session_and_atom(db_session):
    s = MemorySession(id="sess1", contract_id="c1", contract_type="租赁合同")
    db_session.add(s)
    a = MemoryAtom(
        id="atom1",
        session_id="sess1",
        content="用户偏好：违约金超过20%标红",
        kind="preference",
        confidence=0.8,
        status="active",
    )
    db_session.add(a)
    await db_session.commit()
    assert (await db_session.get(MemoryAtom, "atom1")).kind == "preference"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_db_models.py -v`  
Expected: ImportError

- [ ] **Step 3: Add SQLAlchemy models**

在 `database.py` 增加（字段名保持一致）：

```python
class MemorySession(Base):
    __tablename__ = "memory_sessions"
    id = Column(String, primary_key=True)
    contract_id = Column(String, nullable=True)
    contract_type = Column(String, nullable=True)
    status = Column(String, default="open")  # open|closed
    created_at = Column(DateTime, default=func.now())
    closed_at = Column(DateTime, nullable=True)

class MemoryEvent(Base):
    __tablename__ = "memory_events"
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # step|feedback|tool|system
    payload = Column(Text, nullable=False)  # JSON
    created_at = Column(DateTime, default=func.now())

class MemoryAtom(Base):
    __tablename__ = "memory_atoms"
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    kind = Column(String, default="fact")  # fact|preference|constraint|event
    contract_type = Column(String, nullable=True)
    confidence = Column(Float, default=0.5)
    status = Column(String, default="pending")  # pending|active|disabled|rolled_back
    embedding = Column(Text, nullable=True)
    confirm_count = Column(Integer, default=0)
    reject_count = Column(Integer, default=0)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")  # private|team|restricted
    acl_json = Column(Text, nullable=True)  # JSON list of grants
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class MemoryScenario(Base):
    __tablename__ = "memory_scenarios"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    contract_type = Column(String, nullable=True)
    atom_ids = Column(Text, nullable=True)  # JSON list
    confidence = Column(Float, default=0.5)
    status = Column(String, default="pending")
    embedding = Column(Text, nullable=True)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")
    acl_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class MemoryPersona(Base):
    __tablename__ = "memory_personas"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    confidence = Column(Float, default=0.5)
    status = Column(String, default="pending")
    embedding = Column(Text, nullable=True)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")
    acl_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

`init_db` 已用 `Base.metadata.create_all`，新表会自动建；无需删库迁移脚本（开发期可接受）。若需保留旧数据，补充 `scripts/migrate_memory_tables.py` 仅 `CREATE TABLE IF NOT EXISTS`。

召回与写入必须带 `owner_user_id`（默认 `"local"`）；`retrieve` 预留 `principal` 参数（一期可传 `None` 表示单用户不过滤）。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_db_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/models/database.py tests/test_memory_db_models.py
git commit -m ":building_construction: ai-feat(新增) L0-L3 记忆数据表模型"
```

---

### Task 3: MemoryStore 写入

**Files:**
- Create: `server/core/memory/__init__.py`
- Create: `server/core/memory/store.py`
- Test: `tests/test_memory_store.py`

**Interfaces:**
- Consumes: DB models from Task 2
- Produces:
  - `async def start_session(db, *, contract_id, contract_type) -> str`
  - `async def append_event(db, session_id, event_type, payload: dict) -> str`
  - `async def upsert_atom(db, data: dict) -> str`
  - `async def upsert_scenario(db, data: dict) -> str`
  - `async def upsert_persona(db, data: dict) -> str`
  - `async def apply_feedback(db, atom_id, *, confirm: bool) -> MemoryAtom`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_store.py
import pytest
from server.core.memory import store

@pytest.mark.asyncio
async def test_session_event_atom_flow(db_session):
    sid = await store.start_session(db_session, contract_id="c1", contract_type="租赁合同")
    eid = await store.append_event(db_session, sid, "feedback", {"clause_id": "8.1", "from": "yellow", "to": "red"})
    aid = await store.upsert_atom(db_session, {
        "content": "条款违约金偏高时应标红",
        "kind": "preference",
        "session_id": sid,
        "contract_type": "租赁合同",
        "confidence": 0.6,
        "status": "pending",
    })
    await db_session.commit()
    assert sid and eid and aid
    atom = await store.apply_feedback(db_session, aid, confirm=True)
    await db_session.commit()
    assert atom.confirm_count == 1
    assert atom.confidence >= 0.6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_store.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement store.py**

实现要点：
- id 用 `uuid.uuid4().hex`
- `append_event` 的 payload `json.dumps(..., ensure_ascii=False)`
- `apply_feedback(confirm=True)`：`confirm_count += 1`，`confidence = min(1.0, confidence + 0.1)`；若 `confidence >= settings.MEMORY_AUTO_ACTIVATE_THRESHOLD` 则 `status="active"`
- `confirm=False`：`reject_count += 1`，`confidence = max(0.0, confidence - 0.2)`；若 `< 0.3` 则 `status="disabled"`
- `__init__.py` 导出 `store` 模块即可

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_store.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/core/memory/ tests/test_memory_store.py
git commit -m ":necktie: ai-feat(新增) 分层记忆 Store 写入与反馈升降置信度"
```

---

### Task 4: 分层召回与字符预算

**Files:**
- Create: `server/core/memory/retrieve.py`
- Test: `tests/test_memory_retrieve.py`

**Interfaces:**
- Consumes: `RetrieveBudget`, store 中 active 记录
- Produces: `async def retrieve(db, query: str, *, contract_type: str | None, budget: RetrieveBudget | None) -> list[MemoryHit]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_retrieve.py
import pytest
from server.core.memory import store
from server.core.memory.models import RetrieveBudget
from server.core.memory.retrieve import retrieve

@pytest.mark.asyncio
async def test_retrieve_respects_char_budget(db_session):
    for i in range(10):
        await store.upsert_atom(db_session, {
            "content": ("违约金偏好-" + str(i)) * 40,  # 较长文本
            "kind": "preference",
            "contract_type": "租赁合同",
            "confidence": 0.9,
            "status": "active",
        })
    await db_session.commit()
    budget = RetrieveBudget(max_chars=200, max_l1=8, max_l2=0, max_l3=0)
    hits = await retrieve(db_session, "违约金", contract_type="租赁合同", budget=budget)
    assert sum(h.chars() for h in hits) <= 200
    assert all(h.layer == "l1" for h in hits)

@pytest.mark.asyncio
async def test_retrieve_ignores_pending(db_session):
    await store.upsert_atom(db_session, {
        "content": "不应被召回的 pending",
        "status": "pending",
        "confidence": 0.9,
        "contract_type": "租赁合同",
    })
    await db_session.commit()
    hits = await retrieve(db_session, "pending", contract_type="租赁合同")
    assert hits == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_retrieve.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement retrieve.py**

算法（保持简单）：
1. 只取 `status=="active"` 的 persona / scenario / atom
2. 可选 `contract_type` 过滤（atom/scenario；persona 不过滤）
3. 关键词分：query 子串命中 +1；可选 embedding 相似度（`embedding.is_available_async()`，失败则跳过）
4. 分层排序：先填 L3 → L2 → L1，每层不超过 max_*，累计 chars 不超过 max_chars
5. 返回 `list[MemoryHit]`

不要在 retrieve 内调用 LLM。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_retrieve.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/core/memory/retrieve.py tests/test_memory_retrieve.py
git commit -m ":necktie: ai-feat(新增) 分层记忆召回与字符预算裁剪"
```

---

### Task 5: MemoryKernel 门面 + Adapter

**Files:**
- Create: `server/core/memory/kernel.py`
- Create: `server/core/memory/adapters/base.py`
- Create: `server/core/memory/adapters/noop.py`
- Create: `server/core/memory/adapters/__init__.py`
- Modify: `server/core/memory/__init__.py`
- Test: `tests/test_memory_kernel.py`

**Interfaces:**
- Produces:
```python
class MemoryKernel:
    def __init__(self, db: AsyncSession, adapter: TeamMemoryAdapter | None = None): ...
    async def start_session(self, contract_id: str | None, contract_type: str | None) -> str: ...
    async def append_event(self, session_id: str, event_type: str, payload: dict) -> str: ...
    async def retrieve(self, query: str, contract_type: str | None = None) -> list[MemoryHit]: ...
    async def record_feedback(self, *, atom_id: str | None, session_id: str | None, payload: dict, confirm: bool | None) -> dict: ...
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_kernel.py
import pytest
from server.core.memory.kernel import MemoryKernel
from server.core.memory.adapters.noop import NoopTeamMemoryAdapter

@pytest.mark.asyncio
async def test_kernel_retrieve_after_seed(db_session):
    k = MemoryKernel(db_session, adapter=NoopTeamMemoryAdapter())
    sid = await k.start_session("c1", "劳动合同")
    await k.append_event(sid, "step", {"name": "ocr_done"})
    # 直接经 store 写入 active atom 已在 Task3 覆盖；此处 kernel.record_feedback 建 atom
    from server.core.memory import store
    aid = await store.upsert_atom(db_session, {
        "content": "竞业限制补偿金低于月工资30%应标黄",
        "status": "active",
        "confidence": 0.9,
        "contract_type": "劳动合同",
    })
    await db_session.commit()
    hits = await k.retrieve("竞业限制", contract_type="劳动合同")
    assert any("竞业" in h.text for h in hits)
    pushed = await k.adapter.push_assets([])
    assert pushed == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_kernel.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement kernel + adapters**

```python
# adapters/base.py
from typing import Protocol, Any
class TeamMemoryAdapter(Protocol):
    async def push_assets(self, assets: list[dict[str, Any]]) -> int: ...
    async def pull_assets(self, since_iso: str | None = None) -> list[dict[str, Any]]: ...

# adapters/noop.py
class NoopTeamMemoryAdapter:
    async def push_assets(self, assets): return 0
    async def pull_assets(self, since_iso=None): return []
```

`MemoryKernel.retrieve` 使用 `asyncio.wait_for(..., timeout=settings.MEMORY_RETRIEVE_TIMEOUT_SEC)`，超时返回 `[]`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_kernel.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/core/memory/ tests/test_memory_kernel.py
git commit -m ":building_construction: ai-feat(新增) MemoryKernel 门面与 Noop 团队适配器"
```

---

### Task 6: Memory REST API

**Files:**
- Create: `server/api/memory.py`
- Modify: `server/main.py`（`include_router`）
- Test: `tests/test_api_memory.py`

**Interfaces:**
- Produces endpoints listed in spec §10（本 Task 实现会话、atoms 列表、feedback；pending 审核留给 Phase B）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_memory.py
import pytest

@pytest.mark.asyncio
async def test_create_session_and_list_atoms(client, db_session):
    r = await client.post("/api/memory/sessions", json={"contract_id": "c1", "contract_type": "租赁合同"})
    assert r.status_code == 200
    sid = r.json()["id"]
    from server.core.memory import store
    await store.upsert_atom(db_session, {
        "content": "测试原子",
        "status": "active",
        "confidence": 0.9,
        "contract_type": "租赁合同",
    })
    await db_session.commit()
    r2 = await client.get("/api/memory/atoms", params={"q": "原子"})
    assert r2.status_code == 200
    assert len(r2.json()) >= 1

@pytest.mark.asyncio
async def test_feedback_endpoint(client, db_session):
    from server.core.memory import store
    aid = await store.upsert_atom(db_session, {
        "content": "可反馈原子",
        "status": "active",
        "confidence": 0.5,
    })
    await db_session.commit()
    r = await client.post("/api/memory/feedback", json={
        "atom_id": aid,
        "confirm": True,
        "payload": {"note": "正确"},
    })
    assert r.status_code == 200
    assert r.json()["success"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_memory.py -v`  
Expected: 404

- [ ] **Step 3: Implement API + register**

```python
# server/api/memory.py 关键
router = APIRouter(prefix="/api/memory", tags=["memory"])

@router.post("/sessions")
async def create_session(data: SessionCreate, db: AsyncSession = Depends(get_db)):
    k = MemoryKernel(db)
    sid = await k.start_session(data.contract_id, data.contract_type)
    await db.commit()
    return {"id": sid}

@router.get("/atoms")
async def list_atoms(q: str = "", status: str = "active", db: AsyncSession = Depends(get_db)):
    # select MemoryAtom filtered; return list[dict]

@router.post("/feedback")
async def feedback(data: FeedbackBody, db: AsyncSession = Depends(get_db)):
    k = MemoryKernel(db)
    result = await k.record_feedback(atom_id=data.atom_id, session_id=data.session_id, payload=data.payload or {}, confirm=data.confirm)
    await db.commit()
    return {"success": True, **result}
```

在 `main.py` 中 `from server.api.memory import router as memory_router` 并 `app.include_router(memory_router)`（与其他 router 相同位置）。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_memory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/api/memory.py server/main.py tests/test_api_memory.py
git commit -m ":sparkles: ai-feat(新功能) 分层记忆 REST API"
```

---

### Task 7: 桌面端记忆页最小 UI

**Files:**
- Create: `server/static/js/pages/memory.js`
- Modify: `server/static/js/app.js`（导航注册）
- Modify: `server/static/index.html`（若需导航项）

**Interfaces:**
- Consumes: `GET /api/memory/atoms`, `POST /api/memory/feedback`

- [ ] **Step 1: 手动验收清单（无自动化 UI 测试）**

写出页面：列表展示 active atoms；搜索框；确认/拒绝按钮调用 feedback。

- [ ] **Step 2: 实现 memory.js 列表渲染**

参照 `server/static/js/pages/knowledge.js` 的列表与搜索模式，避免整页重渲染导致失焦（防抖 300ms）。

- [ ] **Step 3: 注册路由/导航**

在 `app.js` 增加 `memory` 页面 case，侧边栏增加「记忆」。

- [ ] **Step 4: 手动打开** `http://localhost:8080` 验证列表与反馈按钮

- [ ] **Step 5: Commit**

```bash
git add server/static/js/pages/memory.js server/static/js/app.js server/static/index.html
git commit -m ":lipstick: ai-feat(新增) 桌面端分层记忆浏览与反馈页"
```

---

### Task 8: Phase A 回归

- [ ] **Step 1: Run full related tests**

Run: `pytest tests/test_memory_models.py tests/test_memory_db_models.py tests/test_memory_store.py tests/test_memory_retrieve.py tests/test_memory_kernel.py tests/test_api_memory.py tests/test_knowledge.py -v`  
Expected: 全部 PASS

- [ ] **Step 2: 确认未破坏主分析路径**

Run: `pytest tests/test_agent.py -v`  
Expected: PASS（Agent 尚未接入记忆，行为不变）

- [ ] **Step 3: Commit 若有修复**（无则跳过）

---

## Phase A 完成定义

- L0 session/event、L1 atom、L2 scenario、L3 persona 表可写可读
- `retrieve` 遵守字符与条数预算；pending 不召回
- feedback 升降置信度并可自动激活
- API + 桌面最小页可用
- Team 适配器为 Noop

下一计划：`docs/superpowers/plans/2026-08-10-self-evolving-assets.md`
