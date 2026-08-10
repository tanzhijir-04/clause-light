# LightRAG Wiki Adapter (Phase E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or executing-plans.

**Goal:** 可选接入 HKUDS/LightRAG 作 Wiki/法规双层检索；默认关闭；失败回退现有 wiki.search。

**Architecture:** `server/core/wiki/lightrag_adapter.py` + config `LIGHT_RAG_ENABLED=false`；`wiki.store.search_pages` 可委托 adapter；ACL 先滤 ID 再查（一期单用户跳过滤）。

## Global Constraints

- 新增依赖 `lightrag-hku`（或官方包名）前已在规格确认；若 pip 安装失败，adapter 保持 stub 并 skip 集成测试
- 数据目录 `data/lightrag/`；gitignored
- Commit per task；不 push

### Task 1: Config + adapter stub
- settings.LIGHT_RAG_ENABLED = False
- lightrag_adapter.py: `async def search(query) -> list[str]` — if disabled or import fail return []
- tests/test_lightrag_adapter.py
- Commit: `:building_construction: ai-feat(新增) LightRAG 适配器开关与降级桩`

### Task 2: Wire wiki search optional path
- search_pages: if enabled and adapter returns hits, merge/prefer; else keyword path
- Commit: `:necktie: ai-feat(修改) Wiki 检索可选委托 LightRAG`
