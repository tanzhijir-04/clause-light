# Agent Memory Tools Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让现有三段式 ContractAgent 在开场装配 L3/L2、Stage1 后召回 L1/规则/Skill，并在维度冲突或低置信时按需调用 memory/wiki/skill 工具；分析结束后异步触发 Distill。

**Architecture:** 保持 Prompt Chaining + Parallelization；新增 `server/core/agent_tools.py` 工具函数与预算包装；`ContractAgent.analyze` 接入 MemoryKernel；冲突路径调用工具最多额外 2 次 LLM。不改为全自主 ReAct 循环。

**Tech Stack:** Python ≥3.10, asyncio, 现有 workers, Memory Kernel, Distill, pytest

**Spec:** `docs/superpowers/specs/2026-08-10-self-evolving-memory-design.md`  
**Depends on:** Phase A + Phase B plans

## Global Constraints

- 不破坏 `AnalysisResult` 对外字段；可新增可选 `session_id`
- 无记忆/超时/失败时行为与现网一致（降级空上下文）
- LLM 经 LLMGateway；工具结果必须截断进预算
- 提交格式：`:emoji: ai-feat(类型) 简短说明`
- 工具触发条件仅限：`detect_conflicts` 非空，或某条款 `severity` 缺失/置信标记需要复核

## File Structure

| Path | Responsibility |
|------|----------------|
| `server/core/agent_tools.py` | memory_search / wiki_search / load_skill 包装 |
| `server/core/workers/workers.py` | 接受可选 memory_context 字符串 |
| `server/core/agent.py` | 编排 session、retrieve、tools、distill |
| `server/api/ws.py` / `contracts.py` | 若需回传 session_id |
| `server/core/prompts/analyze_dimension.py` 或 workers 内 prompt | 注入记忆上下文段落 |
| `tests/test_agent_tools.py` | 工具单元测试 |
| `tests/test_agent_memory_integration.py` | mock LLM 集成 |

---

### Task 1: Agent 工具包装

**Files:**
- Create: `server/core/agent_tools.py`
- Test: `tests/test_agent_tools.py`

**Interfaces:**
```python
@dataclass
class ToolBundle:
    memory_text: str
    wiki_text: str
    skill_text: str

async def build_loadout(db, *, contract_type: str, query: str) -> str:
    """L3+L2 开场文本，已裁预算。"""

async def build_stage_context(db, *, contract_type: str, query: str, kb_rules: list[str]) -> str:
    """L1 + rules + matched skill。"""

async def run_conflict_tools(db, *, query: str, contract_type: str) -> ToolBundle:
    """冲突时补充 memory/wiki/skill。"""
```

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_build_loadout_empty_db(db_session):
    from server.core.agent_tools import build_loadout
    text = await build_loadout(db_session, contract_type="租赁合同", query="租赁")
    assert text == "" or isinstance(text, str)

@pytest.mark.asyncio
async def test_build_stage_context_includes_atom(db_session):
    from server.core.memory import store
    from server.core.agent_tools import build_stage_context
    await store.upsert_atom(db_session, {
        "content": "用户是乙方视角",
        "status": "active",
        "confidence": 0.9,
        "contract_type": "租赁合同",
    })
    await db_session.commit()
    text = await build_stage_context(db_session, contract_type="租赁合同", query="租赁", kb_rules=["规则A"])
    assert "乙方" in text or "规则A" in text
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement agent_tools.py**  
内部调用 `MemoryKernel.retrieve`、`skills.store.match_skills`、`wiki.store.search_pages`；拼接为 Markdown 小节；总长截断到 `MEMORY_RETRIEVE_CHAR_BUDGET`。

- [ ] **Step 4: PASS + Commit** `:necktie: ai-feat(新增) Agent 记忆/Wiki/Skill 工具包装`

---

### Task 2: Worker 接受记忆上下文

**Files:**
- Modify: `server/core/workers/workers.py`
- Test: `tests/test_workers_memory_context.py`

**Interfaces:**
- 扩展 `analyze_dimension(..., memory_context: str = "")`
- 扩展 `analyze_dimension_with_context(..., memory_context: str = "")`

- [ ] **Step 1: Failing test — mock llm 捕获 messages 含记忆段落**

```python
@pytest.mark.asyncio
async def test_analyze_dimension_includes_memory_context():
    captured = {}
    class FakeLLM:
        async def chat(self, messages, task="analysis", **kwargs):
            captured["messages"] = messages
            class R: content = "[]"
            return R()
    from server.core.workers.parser import ClauseItem
    from server.core.workers.workers import analyze_dimension
    clauses = [ClauseItem(id="1", type="payment", title="付款", text="验收后90日付款", relevance=["financial"])]
    await analyze_dimension("financial", clauses, FakeLLM(), "租赁合同", [], [], memory_context="用户是乙方")
    blob = json.dumps(captured["messages"], ensure_ascii=False)
    assert "用户是乙方" in blob
```

- [ ] **Step 2–4:** 在构造 user prompt 处增加 `## 记忆与知识\n{memory_context}`；空则不加；提交 `:necktie: ai-feat(修改) 维度 Worker 支持注入记忆上下文`

---

### Task 3: ContractAgent 接入 session + loadout + retrieve

**Files:**
- Modify: `server/core/agent.py`
- Test: `tests/test_agent_memory_integration.py`

**Interfaces:**
- `AnalysisResult.session_id: str = ""`
- analyze 流程：start_session → append ocr/parse events → build_loadout/stage_context → workers

- [ ] **Step 1: Failing integration test with FakeLLM + seeded atom**

断言：`result.session_id` 非空；FakeLLM 某次 messages 含原子内容。  
无 atom 时仍能返回正常 AnalysisResult（不报错）。

- [ ] **Step 2: Run — fail（无 session_id 字段）**

- [ ] **Step 3: Wire agent.py**

```python
# 伪代码关键点
async with async_session_factory() as db:
    kernel = MemoryKernel(db)
    session_id = await kernel.start_session(contract_id, parse_result.contract_type)
    result.session_id = session_id
    await kernel.append_event(session_id, "step", {"name": "parse_done", "clauses": len(parse_result.clauses)})
    memory_context = await build_stage_context(db, contract_type=..., query=full_text[:500], kb_rules=kb_rules)
    await db.commit()

worker_tasks = [
    analyze_dimension(dim, ..., memory_context=memory_context)
    for dim in DIMENSIONS
]
```

知识库检索失败时 `memory_context` 仍可只用 memory hits。

- [ ] **Step 4: PASS + Commit** `:sparkles: ai-feat(新功能) 合同 Agent 装配分层记忆上下文`

---

### Task 4: 冲突路径调用工具

**Files:**
- Modify: `server/core/agent.py`
- Test: `tests/test_agent_conflict_tools.py`

- [ ] **Step 1: Failing test**

构造两维冲突（同 clause_id 不同 risk_level），patch `run_conflict_tools` 返回含 wiki 文本的 ToolBundle，断言 `analyze_dimension_with_context` 收到的 memory_context 含该文本。

- [ ] **Step 2–3:** 在现有 conflicts 循环内：

```python
bundle = await run_conflict_tools(db, query=clause.text, contract_type=...)
extra = "\n".join(x for x in [bundle.memory_text, bundle.wiki_text, bundle.skill_text] if x)
new_risk = await analyze_dimension_with_context(..., memory_context=memory_context + "\n" + extra)
```

限制：每个分析请求冲突工具调用次数 ≤ 2（按冲突 clause 簇计数，超出则跳过工具仅用原 cross_context）。

- [ ] **Step 4: PASS + Commit** `:necktie: ai-feat(修改) 冲突条款按需调用记忆与 Wiki 工具`

---

### Task 5: 结束后异步 Distill

**Files:**
- Modify: `server/core/agent.py`
- Test: `tests/test_agent_distill_trigger.py`

- [ ] **Step 1: Failing test**

patch `distill_from_analysis`，断言 analyze 成功结束时被调用 1 次；distill 抛错不影响 `result.error` 为空。

- [ ] **Step 2–3:**

```python
asyncio.create_task(_safe_distill(...))  # 或 analyze 返回前 await 但吞掉异常
```

推荐：**await + try/except**（SQLite 同进程更简单，避免 session 生命周期问题），超时 30s 可 `wait_for`。

写入 L0 event `distill_done`。

- [ ] **Step 4: Commit** `:sparkles: ai-feat(新功能) 分析结束后触发 Distill 自进化`

---

### Task 6: API/WS 透出 session_id（可选兼容）

**Files:**
- Modify: `server/api/ws.py`（结果消息加 `session_id`）
- Modify: 保存 Analysis 处若有 JSON 字段可存 session_id
- Test: 更新相关 API 测试断言不因多余字段失败

- [ ] **Step 1–5:** 保持旧客户端可忽略新字段；提交 `:sparkles: ai-feat(修改) 分析结果回传记忆 session_id`

---

### Task 7: 文档与回归

**Files:**
- Modify: `docs/AGENT_ARCHITECTURE.md`（增加 Memory Loadout + Tools 小节）
- Modify: `docs/API.md`（memory/skills/wiki 端点）

- [ ] **Step 1: 跑全量相关测试**

```bash
pytest tests/test_agent.py tests/test_agent_tools.py tests/test_agent_memory_integration.py tests/test_agent_conflict_tools.py tests/test_agent_distill_trigger.py tests/test_memory_retrieve.py tests/test_distill_pipeline.py -v
```

Expected: PASS

- [ ] **Step 2: 更新架构文档，去掉过时「不需要 Full Agent」与现状矛盾的表述，改为「Pipeline + 有限工具」**

- [ ] **Step 3: Commit** `:lipstick: ai-feat(修改) 文档同步记忆增强 Agent 架构`

---

## Phase C 完成定义

- 每次分析有 `session_id` 与 L0 事件
- Worker prompt 在有记忆时包含 Loadout/Stage 上下文
- 冲突时最多 2 次工具增强
- 结束后 Distill 失败不影响主结果
- 无记忆时与改造前行为一致

## 全项目收尾检查（A+B+C）

对照规格逐项：

| 规格项 | 对应 Task |
|--------|-----------|
| L0–L3 本地存储与预算召回 | Phase A |
| 规则/Skill/Wiki + 分级生效 | Phase B |
| Pipeline + 按需工具 | Phase C |
| Noop Team adapter | Phase A Task 5 |
| 待审/回滚 | Phase B Task 3/7 |
| 不依赖 TencentDB 可运行 | 全程 |

TencentDB 实接入不在本三份计划内；另开规格再做。
