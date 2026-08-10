# Contract Chat (Phase D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or executing-plans.

**Goal:** 支持针对已分析合同的多轮追问，复用 L0 session、OCR/Markdown 全文与记忆召回。

**Architecture:** 新增 `POST /api/contracts/{id}/chat`；绑定 `memory_session`；工具：读条款摘要、memory_search、wiki_search；LLM 经 LLMGateway；对话事件写入 L0。

**Tech Stack:** FastAPI, MemoryKernel, agent_tools, pytest

## Global Constraints

- 本地优先；无 LightRAG 时 wiki 回退现有 search
- Commit per task；不 push
- 不破坏现有 analyze API

### Task 1: Chat API + L0 events
- Create `server/api/chat.py` or extend contracts.py
- `POST /api/contracts/{contract_id}/chat` body `{message, session_id?}`
- Load contract.ocr_text + latest analysis summary; retrieve memory; call LLM; append L0 events
- tests/test_api_chat.py with FakeLLM
- Commit: `:sparkles: ai-feat(新功能) 合同多轮追问 Chat API`

### Task 2: Desktop minimal chat UI on contract detail
- Add chat panel in contractDetail.js
- Commit: `:lipstick: ai-feat(新增) 合同详情页追问对话入口`
