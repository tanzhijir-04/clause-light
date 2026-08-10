# Self-Evolving Assets (Rules / Skill / Wiki) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现分析后自动提炼候选规则/Skill/Wiki，按置信度分级生效（高置信自动上线可回滚，低置信待审），并提供审核 API。

**Architecture:** 在 Phase A Memory Kernel 之上新增 Distill Pipeline；扩展 `knowledge_rules.status`；新增 `skills`、`wiki_pages`、`wiki_links`、`asset_audit_log`。Distill 只产候选，不直接改写用户可见分析结果。

**Tech Stack:** Python ≥3.10, FastAPI, SQLAlchemy, SQLite, LLMGateway, pytest

**Spec:** `docs/superpowers/specs/2026-08-10-self-evolving-memory-design.md`  
**Depends on:** Phase A plan `2026-08-10-layered-memory-kernel.md`

## Global Constraints

- Python >= 3.10；LLM 必须经 `server/core/llm.py`；Prompt 必须在 `server/core/prompts/`
- 自动上线阈值默认 `settings.MEMORY_AUTO_ACTIVATE_THRESHOLD == 0.75`
- 提交格式：`:emoji: ai-feat(类型) 简短说明`
- 不引入新外部云服务；不做 CodeGraph
- 本计划明确要求扩展表结构与知识库 API 字段（向后兼容旧客户端：保留 `is_active`）

## File Structure

| Path | Responsibility |
|------|----------------|
| `server/models/database.py` | Skill/Wiki/Audit + rules.status |
| `server/core/prompts/distill.py` | Distill prompts |
| `server/core/distill/pipeline.py` | 异步提炼编排 |
| `server/core/distill/activate.py` | 分级生效 / 回滚 / 审计 |
| `server/core/skills/store.py` | Skill CRUD + 触发匹配 |
| `server/core/wiki/store.py` | Wiki CRUD + 链接 |
| `server/core/wiki/ingest.py` | 从 shared/laws|rules 冷启动 |
| `server/core/knowledge.py` | 检索改为 status=active；兼容 is_active |
| `server/api/knowledge.py` | 返回 status；pending 操作可挂 memory 或 knowledge |
| `server/api/skills.py` / `server/api/wiki.py` | REST |
| `server/api/memory.py` | 扩展 pending approve/reject/rollback |
| `tests/test_distill_*.py` 等 | 测试 |

---

### Task 1: 规则 status 迁移兼容

**Files:**
- Modify: `server/models/database.py`（KnowledgeRule 加 `status`）
- Modify: `server/core/knowledge.py`
- Modify: `scripts/migrate_rule_status.py`（新建）
- Test: `tests/test_knowledge.py`（增补）

**Interfaces:**
- Produces: `KnowledgeRule.status`；`search()` 只返回 active

- [ ] **Step 1: Write the failing test**

```python
# 追加到 tests/test_knowledge.py
async def test_search_respects_status_pending(db_session):
    db_session.add(KnowledgeRule(
        id="r_pending", category="租赁", rule_text="pending规则违约金",
        trigger_keywords='["违约金"]', confidence=0.9, is_active=True, status="pending",
    ))
    await db_session.commit()
    engine = KnowledgeEngine(db_session)
    results = await engine.search("违约金", "租赁合同")
    assert all("pending规则" not in r for r in results)
```

注意：若 ORM 尚无 `status` 字段，测试会在构造时报错——先加字段再跑红/绿。

- [ ] **Step 2: Run test — expect fail or error without status filter**

- [ ] **Step 3: Add column + filter**

```python
# KnowledgeRule
status = Column(String, default="active")  # pending|active|disabled|rolled_back
```

`search()` 过滤：`(r.status or ("active" if r.is_active else "disabled")) == "active"`

迁移脚本：对已有行 `UPDATE knowledge_rules SET status='active' WHERE is_active=1` 等。

写规则时同步：`status=active` ⇒ `is_active=True`；`disabled/pending` ⇒ `is_active=False`。

- [ ] **Step 4: pytest tests/test_knowledge.py -v — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m ":necktie: ai-feat(修改) 知识规则增加 status 并兼容 is_active 检索"
```

---

### Task 2: Skill / Wiki / Audit 表

**Files:**
- Modify: `server/models/database.py`
- Test: `tests/test_asset_db_models.py`

- [ ] **Step 1: Failing test — create Skill + WikiPage + WikiLink + AssetAuditLog**

```python
@pytest.mark.asyncio
async def test_skill_wiki_audit_models(db_session):
    from server.models.database import Skill, WikiPage, WikiLink, AssetAuditLog
    db_session.add(Skill(
        id="sk1", name="装修付款审查", version=1, status="pending",
        triggers='{"contract_types":["装修合同"],"keywords":["付款"]}',
        steps='["核对付款节点"]', validation='[]', resources='[]',
        confidence=0.6,
    ))
    db_session.add(WikiPage(id="w1", slug="civil-code-584", title="民法典584条", body="...", status="active"))
    db_session.add(WikiLink(id="l1", from_page_id="w1", to_page_id="w1", rel="related"))
    db_session.add(AssetAuditLog(id="au1", asset_type="skill", asset_id="sk1", action="create", detail="{}"))
    await db_session.commit()
```

- [ ] **Step 2: Run — ImportError**

- [ ] **Step 3: Add models**（字段与上测试一致；`embedding` Text 可空）

- [ ] **Step 4: PASS + Commit** `:building_construction: ai-feat(新增) Skill/Wiki/审计表模型`

---

### Task 3: 分级生效与回滚

**Files:**
- Create: `server/core/distill/activate.py`
- Create: `server/core/distill/__init__.py`
- Test: `tests/test_distill_activate.py`

**Interfaces:**
```python
async def maybe_activate(db, asset_type: str, asset_id: str) -> str  # returns new status
async def approve(db, asset_type: str, asset_id: str) -> None
async def reject(db, asset_type: str, asset_id: str) -> None
async def rollback(db, asset_type: str, asset_id: str) -> None
```

- [ ] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_high_confidence_auto_activates(db_session):
    from server.models.database import KnowledgeRule
    from server.core.distill import activate
    r = KnowledgeRule(id="r1", category="通用", rule_text="高置信规则", confidence=0.8, status="pending", is_active=False)
    db_session.add(r)
    await db_session.commit()
    status = await activate.maybe_activate(db_session, "rule", "r1")
    await db_session.commit()
    assert status == "active"
    assert (await db_session.get(KnowledgeRule, "r1")).is_active is True

@pytest.mark.asyncio
async def test_rollback_sets_rolled_back(db_session):
    from server.models.database import KnowledgeRule
    from server.core.distill import activate
    r = KnowledgeRule(id="r2", category="通用", rule_text="x", confidence=0.9, status="active", is_active=True)
    db_session.add(r)
    await db_session.commit()
    await activate.rollback(db_session, "rule", "r2")
    await db_session.commit()
    assert (await db_session.get(KnowledgeRule, "r2")).status == "rolled_back"
```

每次状态变更写 `AssetAuditLog`。

- [ ] **Step 2–4: 实现、跑通、提交** `:necktie: ai-feat(新增) 资产分级生效与回滚审计`

---

### Task 4: Distill Prompt + Pipeline

**Files:**
- Create: `server/core/prompts/distill.py`
- Create: `server/core/distill/pipeline.py`
- Test: `tests/test_distill_pipeline.py`

**Interfaces:**
```python
async def distill_from_analysis(
    db: AsyncSession,
    llm: LLMGateway,
    *,
    session_id: str,
    contract_type: str,
    clause_summaries: list[dict],
    feedback_events: list[dict] | None = None,
) -> dict  # {"rules": n, "atoms": n, "skills": n, "wiki": n}
```

- [ ] **Step 1: Failing test with mocked LLM**

```python
class FakeLLM:
    async def chat(self, messages, task="analysis", **kwargs):
        class R:
            content = json.dumps({
                "atoms": [{"content": "用户拒绝异地仲裁", "kind": "preference", "confidence": 0.8}],
                "rules": [{"rule_text": "争议解决地应在用户所在地", "category": "通用", "confidence": 0.7, "trigger_keywords": ["仲裁"]}],
                "skills": [],
                "wiki_patches": [],
            }, ensure_ascii=False)
        return R()

@pytest.mark.asyncio
async def test_distill_creates_pending_and_active(db_session):
    from server.core.distill.pipeline import distill_from_analysis
    result = await distill_from_analysis(
        db_session, FakeLLM(), session_id="s1", contract_type="租赁合同",
        clause_summaries=[{"id": "9.1", "risk_level": "red", "issue": "异地仲裁"}],
    )
    await db_session.commit()
    assert result["atoms"] >= 1
    assert result["rules"] >= 1
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

`distill.py` 返回 messages，要求 LLM 输出严格 JSON。  
`pipeline.py`：解析 JSON → 去重（与已有 rule_text / atom content 子串相似则合并升/降置信）→ 写入对应表 status=pending → 对每条调用 `maybe_activate`。  
Skill：仅当 `skills` 非空且 steps≥2 时写入。  
Wiki：`wiki_patches` 有 title+body 则 upsert by slug。

解析失败：打日志并返回全 0，不抛到分析主路径。

- [ ] **Step 4: PASS + Commit** `:sparkles: ai-feat(新功能) 分析后 Distill 提炼候选记忆资产`

---

### Task 5: Skill store + API

**Files:**
- Create: `server/core/skills/store.py`
- Create: `server/api/skills.py`
- Modify: `server/main.py`
- Test: `tests/test_api_skills.py`

**Interfaces:**
```python
async def match_skills(db, contract_type: str, text: str, limit: int = 1) -> list[Skill]
```

- [ ] **Step 1: Write failing API test**

```python
# tests/test_api_skills.py
@pytest.mark.asyncio
async def test_create_and_match_skill(client, db_session):
    r = await client.post("/api/skills", json={
        "name": "装修付款审查",
        "triggers": {"contract_types": ["装修合同"], "keywords": ["付款"]},
        "steps": ["核对付款节点与验收绑定"],
        "validation": [],
        "confidence": 0.9,
        "status": "active",
    })
    assert r.status_code == 200
    m = await client.get("/api/skills/match", params={"contract_type": "装修合同", "q": "进度款付款"})
    assert m.status_code == 200
    assert len(m.json()) >= 1
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `skills/store.py` + `api/skills.py`**

`match_skills`：解析 triggers JSON；`contract_type` 命中或 keywords 出现在 q 中则入选；只返回 `status=active`；`limit` 默认 1。  
Router 前缀 `/api/skills`：`GET ""`、`POST ""`、`GET /match`。注册到 `main.py`。

- [ ] **Step 4: pytest tests/test_api_skills.py -v — PASS**

- [ ] **Step 5: Commit** `:sparkles: ai-feat(新功能) Skill 资产存储与匹配 API`

---

### Task 6: Wiki ingest + API

**Files:**
- Create: `server/core/wiki/store.py`
- Create: `server/core/wiki/ingest.py`
- Create: `server/api/wiki.py`
- Modify: `server/main.py`
- Test: `tests/test_wiki_ingest.py`, `tests/test_api_wiki.py`

- [ ] **Step 1: Write failing ingest test**

```python
# tests/test_wiki_ingest.py
@pytest.mark.asyncio
async def test_ingest_fixture_laws(db_session, tmp_path):
    fixture = tmp_path / "laws.json"
    fixture.write_text(json.dumps([
        {"law_name": "民法典", "article_number": "584", "content": "当事人一方不履行合同义务..."},
        {"law_name": "民法典", "article_number": "585", "content": "约定的违约金低于造成的损失..."},
    ], ensure_ascii=False), encoding="utf-8")
    from server.core.wiki.ingest import ingest_laws
    n = await ingest_laws(db_session, str(fixture))
    await db_session.commit()
    assert n == 2
    from server.core.wiki.store import search_pages
    hits = await search_pages(db_session, "违约金")
    assert any("585" in (h.title + h.body) for h in hits)
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement ingest + store + API**

- `ingest_laws(path)`：每条生成 `slug=f"{law}-{article}"`，`status=active`，body=content  
- `search_pages(db, q, limit=5)`：关键词；可选 embedding  
- `get_page(db, slug, hop=1)`：返回 page + 出链页面摘要（最多 5 个）  
- API：`GET /api/wiki/search?q=`、`GET /api/wiki/pages/{slug}`、`POST /api/wiki/ingest` body `{"path":"shared/laws/civil_code.json"}`

- [ ] **Step 4: pytest tests/test_wiki_ingest.py tests/test_api_wiki.py -v — PASS**

- [ ] **Step 5: Commit** `:sparkles: ai-feat(新功能) 本地 Wiki 冷启动与检索 API`

---

### Task 7: Pending 审核 API

**Files:**
- Modify: `server/api/memory.py`
- Test: `tests/test_api_memory_pending.py`

Endpoints:
- `GET /api/memory/pending` → 聚合 rules/atoms/skills/wiki status=pending
- `POST /api/memory/pending/{asset_type}/{asset_id}/approve`
- `POST /api/memory/pending/{asset_type}/{asset_id}/reject`
- `POST /api/memory/pending/{asset_type}/{asset_id}/rollback`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_pending_approve_rule(client, db_session):
    db_session.add(KnowledgeRule(
        id="rp1", category="通用", rule_text="待审违约金规则",
        confidence=0.5, status="pending", is_active=False,
    ))
    await db_session.commit()
    listed = await client.get("/api/memory/pending")
    assert any(i["id"] == "rp1" for i in listed.json())
    ok = await client.post("/api/memory/pending/rule/rp1/approve")
    assert ok.status_code == 200
    from server.core.knowledge import KnowledgeEngine
    hits = await KnowledgeEngine(db_session).search("违约金", "其他")
    assert any("待审违约金" in h for h in hits)
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Wire endpoints to `distill.activate.approve/reject/rollback`**

`asset_type` 枚举：`rule|atom|skill|wiki`。

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `:necktie: ai-feat(新增) 记忆资产待审与回滚 API`

---

### Task 8: 桌面待审队列 UI

**Files:**
- Modify: `server/static/js/pages/memory.js`（或新建 `pending.js`）
- Modify: `server/static/js/app.js`

- [ ] **Step 1: 在记忆页增加「待审」Tab，fetch `/api/memory/pending`**

- [ ] **Step 2: 每条显示 asset_type/id/摘要；按钮调用 approve/reject/rollback**

- [ ] **Step 3: 操作成功后刷新列表（防抖、保留 Tab 状态）**

- [ ] **Step 4: 手动打开管理面板验证**

- [ ] **Step 5: Commit** `:lipstick: ai-feat(新增) 桌面端资产待审队列`

---

### Task 9: Phase B 回归

```bash
pytest tests/test_knowledge.py tests/test_distill_activate.py tests/test_distill_pipeline.py tests/test_api_skills.py tests/test_wiki_ingest.py tests/test_api_wiki.py tests/test_api_memory_pending.py tests/test_memory_retrieve.py -v
```

Expected: PASS

---

## Phase B 完成定义

- Distill 可从分析结果生成 atoms/rules（及可选 skill/wiki）
- ≥0.75 自动 active 且可 rollback；&lt;0.75 进 pending
- Skill 匹配、Wiki 冷启动与搜索可用
- 审核 API + 桌面待审队列可用

下一计划：`docs/superpowers/plans/2026-08-10-agent-memory-tools.md`
