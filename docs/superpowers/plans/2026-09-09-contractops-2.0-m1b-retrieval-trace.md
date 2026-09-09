# ContractOps 2.0 M1-B 检索 Trace 与引用校验实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不依赖 PostgreSQL、pgvector、Redis 或新增运行时依赖的前提下，为 M1-A 本地检索增加可审计的安全 Trace，并阻止内容哈希不一致的 Citation 进入后续风险结论。

**Architecture:** Trace 作为 `ContextPackage` 的只读 DTO 返回，只保存候选数、ACL 过滤、去重、预算和引用校验计数，不保存查询正文或知识正文。检索器在生成 Citation 时同时校验位置、格式和正文 SHA-256；无效 Citation 被丢弃并把上下文包标记为人工复核。现有 SQLite Retriever 接口保持不变，下阶段 PostgreSQL Retriever 可复用同一 DTO。

**Tech Stack:** Python 3.10+、dataclasses、hashlib、SQLAlchemy async、pytest、pytest-asyncio；不新增依赖，不改数据库表结构。

---

## 文件地图

| 路径 | 作用 |
|---|---|
| `server/modules/rag/schemas.py` | 新增 `RetrievalTrace`，为 `ContextPackage` 增加 Trace 字段 |
| `server/modules/rag/retriever.py` | 统计检索阶段计数，校验 Chunk 正文哈希和 Citation |
| `tests/v2/test_rag_retriever.py` | 验证 Trace、哈希校验和人工复核状态 |
| `docs/TECHNICAL.md` | 记录 Trace 字段和 Citation 安全边界 |

## Task 1：增加稳定的检索 Trace DTO

**Files:**
- Modify: `server/modules/rag/schemas.py`
- Modify: `tests/v2/test_rag_retriever.py`

- [ ] **Step 1: 写失败测试**

在现有检索测试中增加：

```python
async def test_retrieval_trace_reports_filtering_and_budget(v2_session):
    private_chunk = await _add_chunk(
        v2_session,
        content="组织 A 的私有违约责任规则",
        source_label="[内部规则] org-a｜违约规则",
        visibility="private",
        organization_id=uuid.uuid4(),
    )
    await _add_chunk(
        v2_session,
        content="公共来源的违约责任规则",
        source_label="[法律法规] 公共来源｜第一条",
    )
    await _add_chunk(
        v2_session,
        content="公共来源的违约责任规则",
        source_label="[法律法规] 公共来源｜第二条",
    )

    package = await SQLiteRetriever(v2_session).retrieve(
        "违约责任",
        RetrievalContext(organization_id=uuid.uuid4()),
        top_k=5,
        token_budget=80,
    )

    assert package.trace.candidate_count >= package.trace.visible_count
    assert package.trace.acl_filtered_count >= 1
    assert all(hit.chunk_id != private_chunk.id for hit in package.hits)
    assert package.trace.duplicate_count >= 1
    assert package.trace.returned_count == len(package.hits)
    assert package.trace.budget_skipped_count >= 0
    assert package.trace.query_chars == len(package.query)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_retriever.py::test_retrieval_trace_reports_filtering_and_budget -q --no-cov`

Expected: FAIL，因为 `ContextPackage` 尚无 `trace` 字段。

- [ ] **Step 3: 实现最小 Trace DTO**

在 `schemas.py` 的 `ContextPackage` 前增加：

```python
@dataclass(frozen=True)
class RetrievalTrace:
    """检索过程的安全计数，不保存查询或知识正文。"""

    query_chars: int = 0
    candidate_count: int = 0
    acl_filtered_count: int = 0
    visible_count: int = 0
    scored_count: int = 0
    duplicate_count: int = 0
    budget_skipped_count: int = 0
    invalid_citation_count: int = 0
    returned_count: int = 0
```

给 `ContextPackage` 增加：

```python
trace: RetrievalTrace = field(default_factory=RetrievalTrace)
```

保留原有字段和默认值，确保已有调用方无需传入 Trace。

- [ ] **Step 4: 运行 DTO 测试**

Run: `python -m pytest tests/v2/test_rag_retriever.py::test_retrieval_trace_reports_filtering_and_budget -q --no-cov`

Expected: 仍可能因计数尚未填充而失败；失败信息应只涉及计数值，不应是导入错误。

## Task 2：在 SQLite Retriever 中填充 Trace 并加强 Citation 校验

**Files:**
- Modify: `server/modules/rag/retriever.py`
- Modify: `tests/v2/test_rag_retriever.py`

- [ ] **Step 1: 写 Citation 哈希失败测试**

增加一个测试，先摄取或直接写入一个正文为 `"违约责任"`、但 `content_sha256` 为错误 64 位摘要的 Chunk：

```python
async def test_invalid_content_hash_is_dropped_and_requires_review(v2_session):
    chunk = await _add_chunk(
        v2_session,
        content="违约责任",
        source_label="[法律法规] 测试法｜第一条",
    )
    chunk.content_sha256 = "0" * 64
    await v2_session.flush()

    package = await SQLiteRetriever(v2_session).retrieve(
        "违约责任",
        RetrievalContext(organization_id=None),
    )

    assert package.hits == ()
    assert package.requires_human_review is True
    assert package.trace.invalid_citation_count == 1
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_retriever.py::test_invalid_content_hash_is_dropped_and_requires_review -q --no-cov`

Expected: FAIL，因为当前 `_citation()` 只检查摘要长度，没有比较正文摘要，也没有把无效引用计入人工复核。

- [ ] **Step 3: 实现最小检索计数和哈希校验**

在 `retriever.py` 中：

1. 导入 `hashlib` 和 `RetrievalTrace`。
2. `_citation()` 中增加：

```python
expected_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
if chunk.content_sha256 != expected_hash:
    return None
```

3. 检索开始时设置 `candidate_count = len(entries)`；每个不可见条目增加 `acl_filtered_count`，可见条目增加 `visible_count`；产生有效评分时增加 `scored_count`。
4. 生成 Citation 失败时增加 `invalid_citation_count`。
5. 去重跳过时增加 `duplicate_count`；预算不足跳过时增加 `budget_skipped_count`；成功加入命中后更新 `returned_count`。
6. 返回 `ContextPackage` 时填入 `RetrievalTrace`，并将：

```python
requires_human_review=resolution.requires_human_review or invalid_citation_count > 0
```

无效引用不能用原始内容作为降级 Citation，也不能让检索请求整体抛异常。

- [ ] **Step 4: 运行 Trace 和 Retriever 测试**

Run: `python -m pytest tests/v2/test_rag_retriever.py -q --no-cov`

Expected: 所有 Retriever 测试通过；Trace 计数与命中列表一致。

- [ ] **Step 5: Commit**

```powershell
git add server/modules/rag/schemas.py server/modules/rag/retriever.py tests/v2/test_rag_retriever.py
git commit -m ":shield: ai-feat(新增) 增加检索Trace与引用哈希校验"
```

## Task 3：补运行文档并完成本阶段回归

**Files:**
- Modify: `docs/TECHNICAL.md`
- Modify: `tests/v2/test_rag_retriever.py` only if the final regression exposes a defect

- [ ] **Step 1: 文档化安全 Trace**

在 RAG 或数据安全章节加入以下准确说明：

```markdown
### M1-B 检索 Trace 与引用校验

本地 Retriever 返回的 `ContextPackage.trace` 只包含检索阶段计数：候选数、ACL 过滤数、可见数、评分数、去重数、预算跳过数、无效引用数和最终命中数，不保存查询正文或知识正文。

每个 Citation 都会重新计算 Chunk 正文的 SHA-256；摘要不一致的 Chunk 会被丢弃，并把 ContextPackage 标记为 `requires_human_review=true`。这保证后续风险结论不会引用已被篡改或元数据失配的正文。
```

- [ ] **Step 2: 运行本地回归**

Run: `python -m pytest tests/v2/test_rag_*.py -q --no-cov`

Expected: M1-A 与 M1-B RAG 测试全部通过。

Run: `python -m ruff check server/modules/rag tests/v2 --select E4,E7,E9,F --ignore E402,F401,F541,F821,F811`

Expected: `All checks passed!`

- [ ] **Step 3: Commit**

```powershell
git add docs/TECHNICAL.md
git commit -m ":memo: ai-feat(新增) 记录M1-B检索安全边界"
```

## 完成定义

- [ ] `ContextPackage` 向后兼容并携带不含正文的 Trace；
- [ ] Trace 能区分 ACL 过滤、有效评分、去重、预算跳过和最终命中；
- [ ] Citation 必须通过正文 SHA-256 校验；
- [ ] 无效 Citation 被丢弃并触发人工复核；
- [ ] M1-A 原有测试不回归；
- [ ] 不新增运行时依赖、不改数据库表、不连接远端服务；
- [ ] 代码、测试和文档分别形成可独立回滚的提交。
