# Document Ingress (AnyDoc + PaddleOCR) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将上传从「仅 PDF/图片」扩展为办公文档 + 图片；文字档走本地 AnyDoc 转 Markdown，图片与扫描件自动走 PaddleOCR。

**Architecture:** 新增 `DocumentIngress` 统一入口；按魔数/扩展名路由；AnyDoc 失败的 PDF 降级现有 PyMuPDF→Paddle。不调用 Firecrawl 云端 Parse。

**Tech Stack:** Python ≥3.10, FastAPI, `firecrawl-anydoc`, 现有 PaddleOCR + PyMuPDF, pytest

**Spec:** `docs/superpowers/specs/2026-08-10-self-evolving-memory-design.md` §3.0  
**Agent 工作流:** `AGENTS.md`（每完成一个 Task 立即 commit）

## Global Constraints

- 新增依赖仅 `firecrawl-anydoc`（用户已确认）；禁止默认云端 Parse
- 不破坏 `AnalysisResult.ocr_text` 字段名（内容可为 Markdown）
- 上传白名单与前端 `accept` 同步扩展
- Commit：`:emoji: ai-feat(类型) …`；默认不 push

## File Structure

| Path | Responsibility |
|------|----------------|
| `server/core/document_ingress.py` | 路由 + `DocumentResult` |
| `server/core/ocr.py` | 保留 Paddle/PyMuPDF；供 Ingress 调用 |
| `server/api/contracts.py` | 扩展允许的扩展名 |
| `server/static` / `mobile` | 上传 accept 扩展 |
| `requirements.txt` | 增加 firecrawl-anydoc |
| `tests/test_document_ingress.py` | 路由与降级测试 |

---

### Task 1: 依赖与 DocumentResult

**Files:**
- Modify: `requirements.txt`
- Create: `server/core/document_ingress.py`（先只放 dataclass + 常量）
- Test: `tests/test_document_ingress.py`

- [ ] **Step 1: Write failing test**

```python
from server.core.document_ingress import DocumentResult, OFFICE_EXTENSIONS

def test_document_result_fields():
    r = DocumentResult(full_text="# 合同", markdown="# 合同", source="anydoc", confidence_avg=1.0)
    assert r.source == "anydoc"
    assert ".docx" in OFFICE_EXTENSIONS
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Add dependency + models**

`requirements.txt` 增加：`firecrawl-anydoc`

```python
# document_ingress.py
from dataclasses import dataclass, field
OFFICE_EXTENSIONS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt", ".ods", ".odp", ".rtf", ".epub", ".csv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
PDF_EXTENSIONS = {".pdf"}

@dataclass
class DocumentResult:
    full_text: str = ""
    markdown: str = ""
    source: str = "anydoc"  # anydoc|paddle|hybrid|pymupdf
    confidence_avg: float = 0.0
    pages: list[dict] = field(default_factory=list)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `:building_construction: ai-feat(新增) DocumentIngress 模型与 AnyDoc 依赖声明`

---

### Task 2: AnyDoc 转换封装

**Files:**
- Modify: `server/core/document_ingress.py`
- Test: `tests/test_document_ingress.py`（可用最小 fixture docx/md 或 mock）

- [ ] **Step 1: Failing test with mock**

```python
@pytest.mark.asyncio
async def test_anydoc_path_returns_markdown(tmp_path, monkeypatch):
    f = tmp_path / "a.docx"
    f.write_bytes(b"PK\x03\x04fake")  # 或跳过真实解析改 mock
    from server.core import document_ingress as di
    async def fake_anydoc(path: str) -> str:
        return "# 标题\n条款一"
    monkeypatch.setattr(di, "_convert_with_anydoc", fake_anydoc)
    # 强制走 office 分支
    result = await di.ingest(str(f), force_route="anydoc")
    assert "条款一" in result.full_text
    assert result.source == "anydoc"
```

- [ ] **Step 2–3:** 实现 `_convert_with_anydoc(path) -> str`（同步库则 `asyncio.to_thread`）；`ingest()` 调度。

查阅当前 `firecrawl-anydoc` Python API（`convert` / `from_path`），以官方为准包装一层。

- [ ] **Step 4: PASS + Commit** `:necktie: ai-feat(新增) AnyDoc 本地文档转 Markdown`

---

### Task 3: 路由 — 图片/扫描 → Paddle，文字档 → AnyDoc

**Files:**
- Modify: `server/core/document_ingress.py`
- Modify: `server/core/ocr.py`（导出供 Ingress 复用的方法，避免复制）
- Test: `tests/test_document_ingress.py`

路由规则：
1. 扩展名 ∈ IMAGE → `OCREngine.recognize` → source=`paddle`
2. 扩展名 ∈ OFFICE → AnyDoc；失败 raise/返回空再由上层处理
3. PDF：先 AnyDoc（或先 PyMuPDF 探文字长度 ≥100）；不足则 Paddle；可 `hybrid`
4. `force_route` 仅测试用

- [ ] **Step 1: Tests for image→paddle mock、pdf short text→paddle、docx→anydoc**

- [ ] **Step 2–4: Implement + PASS**

- [ ] **Step 5: Commit** `:necktie: ai-feat(新增) 文档入口按类型自动路由 AnyDoc 或 PaddleOCR`

---

### Task 4: Agent + 上传 API 接入

**Files:**
- Modify: `server/core/agent.py`（OCR 步骤改调 `document_ingress.ingest`）
- Modify: `server/api/contracts.py`（扩展名白名单）
- Test: `tests/test_api_contracts.py` 或新增用例允许 `.docx`

现有白名单：

```python
(".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff")
```

扩展为包含 OFFICE_EXTENSIONS + `.webp` + `.tif`。

- [ ] **Step 1: Failing API test — upload .docx 不再 400 unsupported**

- [ ] **Step 2–3: Wire agent + API**

- [ ] **Step 4: PASS `tests/test_agent.py`（mock ingest）**

- [ ] **Step 5: Commit** `:sparkles: ai-feat(新功能) 分析链路支持办公文档上传与解析`

---

### Task 5: 前端 accept 扩展

**Files:**
- Modify: 桌面上传相关 JS/HTML
- Modify: `mobile` 选文件类型（若有）

- [ ] **Step 1: 搜索 `accept=` / `application/pdf` 出现点**

- [ ] **Step 2: 扩展为文档 + 图片 MIME/扩展名**

- [ ] **Step 3: 手动点选验证 UI 可选 docx**

- [ ] **Step 4: Commit** `:lipstick: ai-feat(修改) 上传控件支持文档与图片`

---

### Task 6: 回归

```bash
pytest tests/test_document_ingress.py tests/test_agent.py tests/test_api_contracts.py tests/test_ocr.py -v
```

Expected: PASS；无 AnyDoc wheel 的 CI 环境可用 mock 跳过真实转换（标记 `anydoc`）。

- [ ] **Step 1: 跑测试**
- [ ] **Step 2: 若有修复再 commit**

---

## 完成定义

- 可上传 docx 等办公文档并进入分析
- 图片与扫描 PDF 仍自动 Paddle
- 文字 PDF 优先 AnyDoc/文字层，失败可降级
- 未使用 Firecrawl 云端 API
