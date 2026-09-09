# ContractOps 2.0 M1-A Local RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不依赖 Docker、远端 PostgreSQL/pgvector 或 Redis 的情况下，交付法规/规则本地摄取、来源可追溯检索、冲突复核和固定评测闭环。

**Architecture:** 新增 `server/modules/rag` 模块，使用 M0 的 SQLAlchemy Base 和 session。SQLite 后端负责本阶段的关键词检索及可选本地 Embedding；上层只依赖 `Retriever`、`Citation` 和 `ContextPackage`，下周可替换为 PostgreSQL 全文检索、pgvector、RRF 和 Rerank。旧 v1 知识库模型、检索逻辑和 API 保持不变。

**Tech Stack:** Python 3.10+、FastAPI 项目现有 SQLAlchemy async、Alembic、SQLite、Pydantic、pytest、pytest-asyncio、pytest-cov、现有 Embedding 引擎；本阶段不新增运行时依赖。

**规格：** `docs/superpowers/specs/2026-09-09-contractops-2.0-m1a-local-rag-design.md`

---

## 文件地图

| 路径 | 作用 |
|---|---|
| `server/modules/rag/models.py` | `KnowledgeDocument`、`KnowledgeChunk` 模型 |
| `server/modules/rag/schemas.py` | 检索上下文、命中、来源和上下文包 DTO |
| `server/modules/rag/repository.py` | 幂等写入、活动版本和 ACL 查询 |
| `server/modules/rag/chunking.py` | 文本规范化、分块和来源位置 |
| `server/modules/rag/ingest.py` | law/rule JSON 校验和摄取 |
| `server/modules/rag/retriever.py` | SQLite 关键词/可选 Embedding 检索 |
| `server/modules/rag/conflicts.py` | 来源优先级、显式冲突组和人工复核状态 |
| `server/modules/rag/evaluation.py` | 固定评测集和 Recall/MRR 指标 |
| `scripts/ingest_m1_sources.py` | dry-run 和正式摄取命令 |
| `tests/fixtures/rag/` | 最小法规、规则和评测样例 |
| `tests/v2/test_rag_*.py` | M1-A 单元和 SQLite 集成测试 |
| `migrations/versions/20260909_0002_m1a_rag.py` | M1-A 表结构迁移 |

旧模型注册方式沿用 `migrations/env.py` 的显式 import；不要修改 `server/models/database.py` 的 v1 表定义。

## Task 1: 建立 RAG 模型和迁移

**Files:**
- Create: `server/modules/rag/__init__.py`
- Create: `server/modules/rag/models.py`
- Modify: `migrations/env.py`
- Create: `migrations/versions/20260909_0002_m1a_rag.py`
- Test: `tests/v2/test_rag_models.py`

- [ ] **Step 1: 写模型失败测试**

在 `tests/v2/test_rag_models.py` 建立 `v2_session` 测试，创建一个公共 `KnowledgeDocument` 和两个 `KnowledgeChunk`，断言：

```python
document = KnowledgeDocument(
    source_type="law",
    source_key="shared/laws/civil_code.json",
    source_title="中华人民共和国民法典",
    content_sha256="a" * 64,
    status="active",
    metadata_json={"effective_date": "2021-01-01"},
)
chunk = KnowledgeChunk(
    document_id=document.id,
    ordinal=0,
    heading="第四百六十九条",
    content="当事人订立合同，可以采用书面形式。",
    source_start=0,
    source_end=20,
    content_sha256="b" * 64,
    visibility="public",
    metadata_json={"source_ref": "第四百六十九条", "topic_tags": ["合同形式"]},
)
assert chunk.source_start < chunk.source_end
assert chunk.visibility == "public"
```

再测试相同 `source_key + content_sha256` 的数据库唯一约束，以及 Chunk 必须关联文档。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_models.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing `KnowledgeDocument`。

- [ ] **Step 3: 写最小模型实现**

使用现有 M0 风格的 `Mapped`、`mapped_column`、`TimestampMixin` 和 `uuid.UUID`：

```python
class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("source_key", "content_sha256", name="uq_knowledge_documents_source_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_key: Mapped[str] = mapped_column(String(500))
    source_title: Mapped[str] = mapped_column(String(300))
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunks_document_ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    ordinal: Mapped[int]
    heading: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    source_start: Mapped[int]
    source_end: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    embedding_json: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    visibility: Mapped[str] = mapped_column(String(24), default="public", index=True)
    acl_json: Mapped[list[str] | None] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
```

Use `JSON` instead of a PostgreSQL-only vector type so `Base.metadata.create_all()` works in local SQLite. The next migration can add a pgvector projection without changing these DTOs.

- [ ] **Step 4: 注册模型和编写 Alembic revision**

Add `import server.modules.rag.models  # noqa: F401` to `migrations/env.py`. Create revision `20260909_0002` with `down_revision = "20260909_0001"`, creating both tables, the unique constraints, the document/chunk indexes, and dropping them in reverse order in `downgrade()`.

- [ ] **Step 5: 运行模型测试**

Run: `python -m pytest tests/v2/test_rag_models.py -q`

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
git add server/modules/rag/__init__.py server/modules/rag/models.py migrations/env.py migrations/versions/20260909_0002_m1a_rag.py tests/v2/test_rag_models.py
git commit -m ":card_file_box: ai-feat(新增) 建立M1-A知识文档与分块模型"
```

## Task 2: 实现来源元数据和语义完整分块

**Files:**
- Create: `server/modules/rag/chunking.py`
- Create: `server/modules/rag/schemas.py`
- Create: `tests/fixtures/rag/sample_law.json`
- Create: `tests/fixtures/rag/sample_rules.json`
- Test: `tests/v2/test_rag_chunking.py`

- [ ] **Step 1: 写失败测试**

测试规范化和来源标签：

```python
def test_canonicalize_text_normalizes_line_endings_and_offsets():
    canonical = canonicalize_text("甲\r\n\r\n  乙  ")
    assert canonical.text == "甲\n乙"
    assert canonical.original_to_normalized is not None


def test_law_record_keeps_article_as_one_chunk():
    chunks = chunk_law_record({
        "law_name": "测试法",
        "article_number": "第一条",
        "content": "当事人应当按照约定履行义务。",
        "source_url": "https://example.invalid/law.pdf",
        "tags": ["履行"],
    })
    assert len(chunks) == 1
    assert chunks[0].source_label == "[法律法规] 测试法｜第一条"
    assert chunks[0].topic_tags == ["履行"]


def test_long_content_splits_only_at_sentence_boundaries():
    content = "第一句。" * 250
    chunks = chunk_text(content, heading="第一条", max_chars=800, overlap_chars=80)
    assert len(chunks) > 1
    assert all(chunk.content.strip() for chunk in chunks)
    assert all(chunk.source_start < chunk.source_end for chunk in chunks)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_chunking.py -q`

Expected: FAIL because the chunking DTOs and functions do not exist。

- [ ] **Step 3: 定义稳定 DTO 和规范化函数**

`schemas.py` 中定义 `IngestedChunk`，至少包含 `heading`、`content`、`source_ref`、`source_url`、`source_label`、`topic_tags`、`source_start`、`source_end`、`metadata`。`canonicalize_text()` 将 CRLF/CR 转为 LF、去除行首尾多余空白、压缩连续空行，并返回规范化文本和可用于定位的坐标信息。

- [ ] **Step 4: 实现边界感知分块**

`chunk_text()` 的固定规则：内容不超过 800 字符时原样保留；超过时优先在 `。！？；\n` 后切分，找不到边界才在 800 字符处切分；后续 Chunk 最多从前一个 Chunk 取 80 字符重叠；每个 Chunk 的 `source_start/source_end` 使用规范化全文坐标。

`chunk_law_record()` 生成来源：

```python
source_label = f"[法律法规] {law_name}｜{article_number}"
```

`chunk_rule_record()` 生成来源：

```python
source_label = f"[内部规则] {source_key}｜{category}规则第{ordinal + 1}条"
```

原始 `tags` 只写入 `topic_tags`；不得把主题标签替换来源标签。

- [ ] **Step 5: 运行测试并检查位置单调性**

Run: `python -m pytest tests/v2/test_rag_chunking.py -q`

Expected: PASS；相邻 Chunk 的位置单调递增，重叠不超过 80 字符。

- [ ] **Step 6: Commit**

```powershell
git add server/modules/rag/chunking.py server/modules/rag/schemas.py tests/fixtures/rag tests/v2/test_rag_chunking.py
git commit -m ":scissors: ai-feat(新增) 实现M1-A来源分块与位置追踪"
```

## Task 3: 实现法规/规则摄取和幂等版本

**Files:**
- Create: `server/modules/rag/repository.py`
- Create: `server/modules/rag/ingest.py`
- Test: `tests/v2/test_rag_ingest.py`

- [ ] **Step 1: 写失败测试**

覆盖四个行为：成功摄取法规和规则、相同 hash 重复摄取返回原文档、内容变化生成新文档、坏 JSON 整文件拒绝且无半成品。

```python
result1 = await KnowledgeIngestor(session).ingest_file(sample_law_path)
result2 = await KnowledgeIngestor(session).ingest_file(sample_law_path)
assert result1.document_id == result2.document_id
assert result2.created_chunks == 0

changed = sample_law_path.write_text(updated_json, encoding="utf-8")
result3 = await KnowledgeIngestor(session).ingest_file(sample_law_path)
assert result3.document_id != result1.document_id

bad_path.write_text("{not-json", encoding="utf-8")
with pytest.raises(SourceValidationError):
    await KnowledgeIngestor(session).ingest_file(bad_path)
assert await repository.count_documents() == 0
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_ingest.py -q`

Expected: FAIL with missing ingestor/repository symbols。

- [ ] **Step 3: 实现 repository 的幂等写入**

提供以下 async 方法：

```python
find_by_source_hash(source_key: str, content_sha256: str) -> KnowledgeDocument | None
create_document_with_chunks(document: KnowledgeDocument, chunks: list[KnowledgeChunk]) -> None
list_active_chunks(context: RetrievalContext) -> list[KnowledgeChunk]
```

写入前通过 `(source_key, content_sha256)` 查重，写入文档和 Chunk 使用同一 session 事务；由调用方 `session_scope()` 负责 commit/rollback。

- [ ] **Step 4: 实现 JSON 解析和文件级事务**

`KnowledgeIngestor.ingest_file()` 根据路径目录判断 `law`/`rule`，读取 JSON 数组，逐项校验必填字段，构造规范化的 canonical source text，调用 chunking 生成 Chunk，再创建文档。

校验错误统一为 `SourceValidationError(source_key, field, reason)`；异常信息只包含文件路径、字段名和错误类型，不包含正文。文件内任意一项失败时抛出异常，调用方回滚整文件。

- [ ] **Step 5: 运行摄取测试**

Run: `python -m pytest tests/v2/test_rag_ingest.py -q`

Expected: PASS；同源同 hash 无重复，源内容变化不覆盖旧文档。

- [ ] **Step 6: Commit**

```powershell
git add server/modules/rag/repository.py server/modules/rag/ingest.py tests/v2/test_rag_ingest.py
git commit -m ":inbox_tray: ai-feat(新增) 实现M1-A法规规则幂等摄取"
```

## Task 4: 实现 SQLite 检索、ACL、Citation 和 ContextPackage

**Files:**
- Modify: `server/modules/rag/schemas.py`
- Create: `server/modules/rag/retriever.py`
- Test: `tests/v2/test_rag_retriever.py`

- [ ] **Step 1: 写失败测试**

测试命中来源、公共知识、租户隔离、Token Budget 和无 Embedding 降级：

```python
package = await SQLiteRetriever(session, embedding_provider=None).retrieve(
    "违约责任",
    RetrievalContext(organization_id=uuid.uuid4(), contract_type="service"),
    top_k=5,
    token_budget=120,
)
assert package.degraded_mode == "lexical"
assert all(hit.citation.source_label for hit in package.hits)
assert package.total_chars <= 120
assert package.hits[0].citation.content_sha256

private_chunk = make_chunk(visibility="private", acl_json=["org-a"])
org_b_package = await retriever.retrieve("私有规则", RetrievalContext(organization_id=ORG_B))
assert all(hit.chunk_id != private_chunk.id for hit in org_b_package.hits)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_retriever.py -q`

Expected: FAIL with missing Retriever/ContextPackage symbols。

- [ ] **Step 3: 定义检索 DTO**

在 `schemas.py` 中定义：

```python
@dataclass(frozen=True)
class RetrievalContext:
    organization_id: uuid.UUID | None
    contract_type: str | None = None
    allowed_visibility: frozenset[str] = frozenset({"public", "team", "private"})


@dataclass(frozen=True)
class Citation:
    chunk_id: uuid.UUID
    source_label: str
    source_key: str
    source_ref: str | None
    source_start: int
    source_end: int
    content_sha256: str


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: uuid.UUID
    content: str
    score: float
    citation: Citation


@dataclass(frozen=True)
class ContextPackage:
    query: str
    hits: tuple[RetrievalHit, ...]
    total_chars: int
    degraded_mode: str
    degraded_reason: str | None = None
    conflict_detected: bool = False
    requires_human_review: bool = False
```

- [ ] **Step 4: 实现 ACL-first 关键词检索**

先过滤 `status=active`、公共文档或相同 `organization_id`、可见性和 ACL；再做关键词评分。评分固定为：完整查询命中正文 5 分，`heading`/来源主题标签命中 3 分，正文命中 1 分，`confidence` 每 0.1 分加 0.1。分数相同按来源标签和 ordinal 稳定排序。

去重使用 `content_sha256`；加入 ContextPackage 时只加入完整 Chunk，不截断 Chunk。若超过预算，停止加入后续结果。

- [ ] **Step 5: 实现可选 Embedding 评分**

定义 `EmbeddingProvider` Protocol，默认不触发模型下载。传入 provider 时调用现有 `server.core.embedding`，出现缺失、下载或编码异常就保留关键词结果并设置：

```python
degraded_mode = "lexical"
degraded_reason = "embedding_unavailable"
```

本阶段不输出 `pgvector`、`rrf` 或 `rerank` 名称，避免误报能力。

- [ ] **Step 6: 生成并校验 Citation**

Citation 从 Chunk 和 Document 来源字段生成；校验 `source_start < source_end`、内容 hash 为 64 位十六进制、Chunk 状态可见。任何校验失败的命中被丢弃，并将 Package 标为人工复核。

- [ ] **Step 7: 运行测试**

Run: `python -m pytest tests/v2/test_rag_retriever.py -q`

Expected: PASS；所有命中都带来源，ACL 过滤先于排序，预算不越界。

- [ ] **Step 8: Commit**

```powershell
git add server/modules/rag/schemas.py server/modules/rag/retriever.py tests/v2/test_rag_retriever.py
git commit -m ":mag: ai-feat(新增) 实现M1-A本地检索与来源引用"
```

## Task 5: 实现来源优先级和显式冲突复核

**Files:**
- Create: `server/modules/rag/conflicts.py`
- Modify: `server/modules/rag/retriever.py`
- Test: `tests/v2/test_rag_conflicts.py`

- [ ] **Step 1: 写失败测试**

测试优先级和不静默裁决：

```python
result = resolve_conflicts([
    make_hit(source_type="rule", conflict_key="deposit", content="上限为两个月"),
    make_hit(source_type="law", conflict_key="deposit", content="应当合理约定"),
])
assert result.conflict_detected is True
assert result.requires_human_review is True
assert len(result.hits) == 2
assert result.hits[0].citation.source_label.startswith("[法律法规]")
```

还要测试：完全相同的内容只保留一条；没有 `conflict_key` 时不强行声称语义冲突，但仍保留不同来源。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_conflicts.py -q`

Expected: FAIL with missing conflict resolver。

- [ ] **Step 3: 实现来源排序**

优先级按以下 tuple 比较：

```python
(
    scope_match,
    current_effective_version,
    authority_rank,  # law > official_guidance > organization_policy > rule
    verified_at,
)
```

来源元数据不足时使用最低优先级，不推断法律效力。

- [ ] **Step 4: 实现显式冲突组**

只把拥有相同非空 `metadata_json["conflict_key"]` 且内容 hash 不同的命中归入冲突组。没有显式冲突 key 时不做语义矛盾判断；这避免把同主题的互补规则误报成冲突。

冲突结果同时保留各自 Citation，设置 `conflict_detected=True` 和 `requires_human_review=True`。检索器把该状态并入 ContextPackage。

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/v2/test_rag_conflicts.py tests/v2/test_rag_retriever.py -q`

Expected: PASS；冲突不被静默覆盖。

- [ ] **Step 6: Commit**

```powershell
git add server/modules/rag/conflicts.py server/modules/rag/retriever.py tests/v2/test_rag_conflicts.py
git commit -m ":warning: ai-feat(新增) 增加M1-A来源冲突复核"
```

## Task 6: 建立固定评测集和本地指标

**Files:**
- Create: `tests/fixtures/rag/eval_cases.json`
- Create: `server/modules/rag/evaluation.py`
- Test: `tests/v2/test_rag_evaluation.py`

- [ ] **Step 1: 写失败测试和固定样例**

`eval_cases.json` 使用本地法规/规则的来源 key 和条款号，不写未经核实的法律结论。每项结构固定为：

```json
{
  "case_id": "law-contract-form-001",
  "query": "合同采用电子数据形式",
  "expected_sources": [
    {"source_key": "shared/laws/civil_code.json", "source_ref": "第四百六十九条"}
  ],
  "k": 5
}
```

至少加入 8 个案例，覆盖法规、租赁规则、劳动规则、通用规则、无结果查询和来源冲突样例。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/v2/test_rag_evaluation.py -q`

Expected: FAIL because the evaluator does not exist。

- [ ] **Step 3: 实现指标函数**

实现纯函数：

```python
def recall_at_k(expected: set[SourceRef], actual: list[SourceRef], k: int) -> float: ...
def reciprocal_rank(expected: set[SourceRef], actual: list[SourceRef], k: int) -> float: ...
def evaluate_cases(cases, retrieve) -> dict: ...
```

输出固定 JSON 字段：`case_count`、`recall_at_5`、`recall_at_10`、`mrr_at_10`、`duplicate_hits`、`acl_leaks`、`conflict_cases`、`degraded_cases`。空 expected case 只验证不返回无关结果，不参与 Recall 分母。

- [ ] **Step 4: 运行指标测试**

Run: `python -m pytest tests/v2/test_rag_evaluation.py -q`

Expected: PASS；相同输入两次输出 JSON 字段和数值一致。

- [ ] **Step 5: Commit**

```powershell
git add tests/fixtures/rag/eval_cases.json server/modules/rag/evaluation.py tests/v2/test_rag_evaluation.py
git commit -m ":bar_chart: ai-feat(新增) 建立M1-A检索评测指标"
```

## Task 7: 增加本地摄取命令和文档

**Files:**
- Create: `scripts/ingest_m1_sources.py`
- Test: `tests/v2/test_rag_ingest_cli.py`
- Modify: `README.md`
- Modify: `docs/TECHNICAL.md`

- [ ] **Step 1: 写 CLI 失败测试**

验证 `--source-dir`、`--dry-run`、`--database-url` 参数；dry-run 只报告文件数、记录数、Chunk 数和错误数，不写数据库。

- [ ] **Step 2: 实现 CLI**

命令接口：

```powershell
python scripts/ingest_m1_sources.py --source-dir shared --dry-run
python scripts/ingest_m1_sources.py --source-dir shared
```

JSON 输出只包含 `status`、`source_files`、`records`、`chunks`、`created_documents`、`skipped_documents`、`errors`；不输出完整正文。

- [ ] **Step 3: 文档化本机运行方式**

在 README 和 `docs/TECHNICAL.md` 说明：

- 本阶段 SQLite 即可运行；
- 只摄取 `shared/laws` 和 `shared/rules`；
- 来源标签与主题标签的区别；
- 冲突结果必须人工复核；
- Embedding 不可用时的降级状态；
- 下周 PostgreSQL/pgvector/RRF/Rerank 的集成入口；
- 不读取或修改 v1 历史合同数据库。

- [ ] **Step 4: 运行 CLI 测试**

Run: `python -m pytest tests/v2/test_rag_ingest_cli.py -q`

Expected: PASS；dry-run 不改变 SQLite 数据。

- [ ] **Step 5: Commit**

```powershell
git add scripts/ingest_m1_sources.py tests/v2/test_rag_ingest_cli.py README.md docs/TECHNICAL.md
git commit -m ":rocket: ai-feat(新增) 交付M1-A本地知识摄取命令"
```

## Task 8: 完成全量验证和 M1-A 报告

**Files:**
- Create: `docs/superpowers/reports/2026-09-09-contractops-2.0-m1a/`
- Modify: none unless verification exposes a defect

- [ ] **Step 1: 运行新增测试**

Run: `python -m pytest tests/v2/test_rag_*.py -q`

Expected: all M1-A tests PASS。

- [ ] **Step 2: 运行完整回归**

Run: `python -m pytest -q`

Expected: 原有 v1 测试不回归，所有本地可运行测试通过；外部服务缺失时只跳过已标记的集成测试。

- [ ] **Step 3: 运行静态检查**

Run: `python -m ruff check server tests scripts --select E4,E7,E9,F --ignore E402,F401,F541,F821,F841,F811 --output-format concise`

Expected: `All checks passed!`

- [ ] **Step 4: 执行本地摄取和评测**

Run:

```powershell
python scripts/ingest_m1_sources.py --source-dir shared --dry-run
python scripts/ingest_m1_sources.py --source-dir shared
python -m pytest tests/v2/test_rag_evaluation.py -q
```

Expected：7 个源文件可识别；重复执行不新增文档；评测 JSON 稳定输出 Recall/MRR、重复数、ACL 泄漏数和冲突数。

- [ ] **Step 5: 保存专门测试产物**

保存以下文件，不提交 `.coverage`、`htmlcov/` 等生成目录：

- `docs/superpowers/reports/2026-09-09-contractops-2.0-m1a/test-cases.md`
- `docs/superpowers/reports/2026-09-09-contractops-2.0-m1a/pytest-output.txt`
- `docs/superpowers/reports/2026-09-09-contractops-2.0-m1a/test-report.md`

报告必须记录：测试命令、用例数、通过/跳过/失败数、覆盖率、Embedding 模式、评测指标、警告和外部服务未执行原因。

- [ ] **Step 6: Commit**

```powershell
git add docs/superpowers/reports/2026-09-09-contractops-2.0-m1a
git commit -m ":white_check_mark: ai-feat(新增) 保存M1-A本地RAG验收报告"
```

## 完成定义

- [ ] 现有 v1 测试全部通过；
- [ ] M1-A 新测试全部通过；
- [ ] 7 个本地法规/规则源可幂等摄取；
- [ ] 每个命中都有来源标签、来源文件、来源引用和可校验 hash；
- [ ] ACL 在评分前过滤；
- [ ] Embedding 缺失时显式关键词降级；
- [ ] 显式冲突不被覆盖，进入人工复核；
- [ ] 固定评测集能重复输出 Recall@5、Recall@10、MRR@10、重复数和 ACL 泄漏数；
- [ ] 本机流程不要求 Docker、PostgreSQL、pgvector 或 Redis；
- [ ] 报告保存到专门目录；
- [ ] 下周接入真实数据库时只替换检索后端和迁移投影，不改变上层 Citation/ContextPackage 契约。
