# ClauseLight 自进化记忆与知识库 — 设计规格

> 分支：`feat/self-evolving-memory-architecture`  
> 状态：已确认方案（本地 Memory Kernel + HKUDS/LightRAG Wiki 图检索 + 可选 TencentDB 团队层）  
> 落地顺序：A 分层记忆 → A′ Outlines 结构化输出 → B 自进化资产 → C Agent 工具 → D 合同追问对话 → E LightRAG 图检索后端 → 可选 TencentDB

## 1. 背景与目标

### 现状

- OCR → Stage1 解析 → Stage2 五维并行 → Stage3 聚合 已跑通。
- `KnowledgeEngine` 提供规则/法规混合检索；`knowledge_rules.source` 已预留 `auto_learned` / `user_feedback`，但无闭环。
- Agent 为固定 Prompt Chaining Workflow；无跨会话记忆；知识库检索仅用合同前 500 字。

### 目标

让审查 Agent **越用越准**：跨会话继承偏好与经验；规则/Skill/Wiki 可持续沉淀；默认数据仍在本机。记忆管理对标 [TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) 的分层与资产管理理念，**不强制依赖其云服务**。

### 成功标准（整体）

1. 同一用户第二次审查同类合同时，能召回上次纠错/偏好（L1/L3），且注入有字符预算上限。
2. 分析结束后能产生候选规则/Skill/Wiki 片段；高置信可自动 `active`（可回滚），低置信进待审队列。
3. Pipeline 在冲突或低置信时可通过工具按需查 Memory / Wiki / Skill，而非常驻塞满上下文。
4. 本地闭环不依赖 TencentDB；`TeamMemoryAdapter` 接口预留，后期可接团队共享。

## 2. 已确认决策

| 项 | 选择 |
|----|------|
| 部署 | **混合**：本地核心 + 可选 TencentDB 团队层 |
| 进化信号 | 自动提炼候选 + 用户反馈升降置信度 |
| 资产类型 | Chat Memory(L0–L3) + 规则 + Skill + Wiki |
| Agent 形态 | Pipeline 为主 + 按需工具（冲突/低置信时） |
| 生效策略 | **分级**：高置信自动上线可回滚；低置信待审 |
| 实现主干 | 本地 Memory Kernel（SQLite + 现有 embedding） |
| 图检索 | **HKUDS/LightRAG**（Wiki/法规双层检索后端；不取代 Memory Kernel） |
| 结构化输出 | **Outlines（.txt）** 经 `LLMGateway.chat_structured` 约束 Stage1–3 / Distill |
| 多用户 / ACL | 表结构一期预留 `owner_user_id` + `visibility` + ACL；UI/登录后置 |
| 追问对话 | Phase D：合同多轮问答，复用 L0 历史 + LightRAG/Wiki 检索 |
| 文档入口 | **AnyDoc（已确认）**：办公文档/文字 PDF → Markdown；图片与扫描件自动 PaddleOCR |

## 3. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  Web / Mobile：记忆 · 待审 · Wiki · Skill ·（后期）用户/ACL    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  ContractAgent ± Contract Chat（D）                          │
│  Pipeline + Tools；LLMGateway.chat_structured（Outlines）     │
└───────┬─────────────────────┬─────────────────────┬─────────┘
        │                     │                     │
┌───────▼────────┐  ┌─────────▼─────────┐  ┌───────▼──────────┐
│ Memory Kernel  │  │ Rules/Skill/Wiki  │  │ Distill Pipeline │
│ L0–L3 + ACL    │  │                   │  │                  │
└───────┬────────┘  └─────────┬─────────┘  └──────────────────┘
        │            ┌────────▼────────┐
        │            │ LightRAG（E）    │  Wiki/法规图+向量双层
        │            └────────┬────────┘
        └─────────────────────┴──────────► SQLite 权威源
                              │
                    TeamMemoryAdapter → 可选 TencentDB
```

### 模块边界

| 模块 | 职责 | 不负责 |
|------|------|--------|
| `server/core/memory/` | L0–L3、预算召回、会话、**principal ACL 过滤** | OCR、风险评级 |
| `server/core/knowledge.py` | 规则检索/CRUD | L0 对话存储 |
| `server/core/skills/` | Skill 版本与触发 | 通用聊天记忆 |
| `server/core/wiki/` | Wiki 页面/链接/ingest；可委托 LightRAG | 取代 Memory Kernel |
| `server/core/wiki/lightrag_adapter.py` | HKUDS/LightRAG 封装；关闭则回退 | 鉴权、Distill |
| `server/core/distill/` | 提炼候选资产 | 改写用户可见结论 |
| `server/core/llm.py` | 含 Outlines 结构化输出 | 业务编排 |
| `server/core/memory/adapters/` | TencentDB 同步 | 本地权威存储 |
| `ContractAgent` | 编排 + 工具 | 持久化细节 |
| `server/core/document_ingress.py` | 统一文档入口：路由 AnyDoc / Paddle；输出 `full_text`/`markdown` | 风险评级、记忆持久化 |

**A–C 不做**：CodeGraph、完整 Team Hub UI、强制上云、强制 LightRAG。  
**后置**：D 追问对话；E LightRAG 可选开启；多用户登录 UI。  
**已确认可引入依赖**：`firecrawl-anydoc`（本地解析，不用 Firecrawl 托管 Parse API）。

### 3.0 Document Ingress（文档 + 图片）

上传从「仅 PDF/图片」拓展为 **办公文档 + 图片**。

```text
上传文件（按内容魔数检测格式，不盲信扩展名）
  ├─ 图片（png/jpg/jpeg/bmp/tiff/webp）     → PaddleOCR
  ├─ 扫描型 PDF（文字层不足）              → 转图 → PaddleOCR
  └─ 文字 PDF / doc(x) / ppt(x) / xls(x) /
     odt/ods/odp / rtf / epub / csv …     → AnyDoc → Markdown
                                              └─ 作为 full_text 进入 Stage1
```

- 对外统一 `DocumentResult(full_text, markdown, source: anydoc|paddle|hybrid, confidence_avg, pages?)`。
- `OCREngine.recognize` 演进为调用 Ingress，或 Agent 改为调 Ingress（保持 `AnalysisResult.ocr_text` 字段名兼容，内容可为 Markdown）。
- API `accept` 与校验白名单同步扩展；超大文件仍受 `MAX_UPLOAD_SIZE` 限制。
- **禁止**默认走 Firecrawl 云端 Parse；仅本地 `firecrawl-anydoc`。
- AnyDoc 失败且文件为 PDF 时：降级现有 PyMuPDF → Paddle 路径。

## 3.1 LightRAG（HKUDS）集成原则

- **定位**：Wiki/法规/长文档的 low-level + high-level 图检索；服务追问与法规关联。
- **不定位**：不存 L0；不做偏好权威源（仍归 L1/L3）。
- **开关**：`LIGHT_RAG_ENABLED=false` 默认；失败/超时回退 `wiki.search` / `search_laws`。
- **权限**：先按 ACL 得到允许的资产 ID，再交 LightRAG，禁止图检索绕权。
- **依赖**：引入前按 AGENTS.md 澄清确认；数据在 `data/lightrag/`，可删可重建。

### 3.2 Outlines 结构化输出

- `LLMGateway.chat_structured(messages, schema|type, task=...)`。
- 覆盖 Stage1/2/3 与 Distill JSON；Worker 禁止直接 `import outlines`。

### 3.3 多用户与权限

资产表预留 `owner_user_id`、`visibility`（`private|team|restricted`）、`acl_json`。  
`retrieve(..., principal)`：private 仅 owner；team 同队可读；restricted 看 ACL。  
无登录时：`owner_user_id="local"`，召回不过滤（单用户兼容）。

## 4. 分层记忆模型（对标 TencentDB L0–L3）

合同领域映射：

| 层级 | 存什么 | 示例 | 召回时机 |
|------|--------|------|----------|
| **L0 Conversation** | 一次分析会话的原始事件流（步骤、用户纠错原文、工具调用摘要） | OCR 完成、用户把条款 8.1 从 yellow 改为 red | 审计、溯源、再蒸馏 |
| **L1 Atom** | 可执行原子事实/偏好/约束 | 「用户是乙方」「违约金>20% 一律标红」「不接受外地仲裁」 | Stage2/工具检索主通道 |
| **L2 Scenario** | 按合同类型/场景聚合的知识块 | 「装修合同 · 付款节点」场景摘要 + 关联 atom ids | 同类合同冷启动 |
| **L3 Persona / Core** | 长期稳定画像 | 「个人房东审查视角」「偏好通俗解释、厌恶霸王条款」 | 每次分析开头轻量注入 |

### 召回策略

1. **先 ACL 后检索**：按 `principal` 过滤可见资产，再关键词 + 向量 + RRF。
2. 查询：复用 `server/core/embedding.py`；失败则纯关键词。
3. **预算硬限制**（可配置）：默认合计 ≤ 3000 汉字；条数 L3≤3、L2≤2、L1≤8、Wiki≤3、Skill≤1、Rules≤5。
4. 超时：单次 retrieve ≤ 3s，失败则空结果继续分析。
5. Wiki/法规高阶查询（Phase E）：可走 LightRAG 双层检索，结果仍受预算与 ACL 约束。

### 写入路径

- **同步**：分析开始创建 L0 session；关键步骤 append event。
- **异步 Distill**：分析结束或用户反馈后，LLM 提炼 L1 候选；周期合并进 L2；稳定偏好晋升 L3。
- **用户反馈**：改 risk_level / 点赞踩 / 编辑建议 → 立即写 L0 event + 调整关联规则/原子 `confidence` / `confirm_count` / `reject_count`。

## 5. 知识资产

### 5.1 规则（升级现有 `knowledge_rules`）

新增/明确字段语义：

- `status`: `pending` | `active` | `disabled` | `rolled_back`
- `confidence`: 0–1；用户确认 +0.1（封顶 1.0），拒绝 −0.2（触底 pending 或 disabled）
- `source`: `manual` | `auto_learned` | `user_feedback` | `import`
- `auto_activate_threshold`: 配置项，默认 `0.75`；≥ 阈值且校验通过 → `active`
- 保留 `confirm_count` / `reject_count` / `usage_count`

检索仅命中 `status=active`（兼容旧 `is_active=True`）。

### 5.2 Skill

结构化可复用审查套路（非纯 Prompt）：

```json
{
  "id": "...",
  "name": "装修合同付款条款审查",
  "version": 1,
  "status": "pending|active|disabled",
  "triggers": {"contract_types": ["装修合同"], "keywords": ["付款", "进度款"]},
  "steps": ["核对付款节点与验收绑定", "检查逾期利息年化", "..."],
  "validation": ["输出须含条款 id", "须给出修改建议"],
  "resources": []
}
```

Stage2 或工具 `load_skill` 在触发匹配时注入 steps（受预算约束）。

### 5.3 Wiki

本地精简版（Karpathy LLM Wiki 思路）：

- `wiki_pages`：title、slug、body、embedding、status、source
- `wiki_links`：from_page → to_page、rel（`cites` / `related` / `supersedes`）
- 冷启动：从 `shared/laws/*.json`、`shared/rules/*.json` ingest 成页面
- Agent 工具：`wiki_search`、`wiki_get`（沿链接下钻最多 1 跳，防爆炸）

不做 CodeGraph。

## 6. Distill 与分级生效

```
分析完成 / 用户反馈
        │
        ▼
 Distill Job（后台）
        │
        ├─→ 候选 L1 Atom
        ├─→ 候选 Rule
        ├─→ 候选 Skill（跨多次同类成功模式时）
        └─→ 候选 Wiki 补丁（新法条引用、新解释）
                │
                ▼
        confidence 估算 + 去重
                │
        ┌───────┴────────┐
        │ ≥ threshold    │ < threshold
        ▼                ▼
   status=active     status=pending
   （可一键回滚）      （待审队列）
```

- 自动上线必须可 `rolled_back`，并写审计日志到 L0。
- 待审 API：`list pending` / `approve` / `reject`。
- Distill Prompt 必须在 `server/core/prompts/`，经 `LLMGateway` 调用。

## 7. Agent 集成（Phase C）

保持现有三段式 Pipeline，增加：

1. **开场 Loadout**：注入精简 L3 + 匹配 L2 摘要（预算内）。
2. **Stage1 后 retrieve**：按条款簇/合同类型取 L1 + Rules + 可选 Skill。
3. **工具（仅冲突或 severity 不确定时）**：
   - `memory_search(query, layers)`
   - `wiki_search` / `wiki_get`
   - `load_skill(skill_id)`
4. **结束后**：写 L0 + 触发 Distill（异步，不阻塞返回结果）。

总 LLM 次数目标：基线 6–7 次不变；工具路径额外 ≤ 2 次/冲突条款簇。

## 8. TeamMemoryAdapter（后期）

```python
class TeamMemoryAdapter(Protocol):
    async def push_assets(self, assets: list[MemoryAsset]) -> None: ...
    async def pull_assets(self, since: datetime | None) -> list[MemoryAsset]: ...
```

- 本地 SQLite 始终是单机权威源。
- 适配器只同步 `visibility=team` 且用户显式开启的资产。
- Phase A–C 只实现 `NoopTeamMemoryAdapter` + 接口测试双倍。

## 9. 数据模型（新增/变更）

> 本规格**明确要求**扩展数据库表结构（覆盖 AGENT.md「除非明确要求」条款）。

新增表（建议）：

- `memory_sessions` — L0 会话（含 `owner_user_id`）
- `memory_events` — L0 事件
- `memory_atoms` — L1（含 `owner_user_id` / `visibility` / `acl_json`）
- `memory_scenarios` — L2（同上）
- `memory_personas` — L3（同上）
- `skills` — Skill 资产（同上）
- `wiki_pages` / `wiki_links` — Wiki（同上）
- `asset_audit_log` — 自动上线/回滚/审核审计
- `users` / `teams` — **可后置建表**；一期用常量 `local` 用户

变更：

- `knowledge_rules` 增加 `status`、`owner_user_id`、`visibility`、`acl_json`（迁移：`is_active=True` → `active`）

## 10. API 草图

| Method | Path | 说明 |
|--------|------|------|
| GET/POST | `/api/memory/sessions` | 会话 |
| GET | `/api/memory/atoms` | L1 列表/搜索 |
| POST | `/api/memory/feedback` | 用户纠错反馈 |
| GET | `/api/memory/pending` | 待审资产聚合 |
| POST | `/api/memory/pending/{id}/approve` | 审核通过 |
| POST | `/api/memory/pending/{id}/reject` | 拒绝 |
| POST | `/api/memory/pending/{id}/rollback` | 回滚自动上线项 |
| CRUD | `/api/skills` | Skill |
| GET/POST | `/api/wiki/pages` | Wiki |
| GET | `/api/wiki/search` | Wiki 搜索 |
| 现有 | `/api/knowledge/*` | 规则（扩展 status） |

不破坏现有 contracts / ws 分析主路径签名；仅扩展可选字段（如 `session_id`）。

## 11. 前端

桌面 `server/static` 增加/扩展：

- 记忆管理页：分层浏览、待审队列、回滚
- 知识库页：规则 status 展示
- Skill / Wiki 简易列表与详情

手机端 Phase A–C 仅需反馈入口（改风险等级时调 `/api/memory/feedback`）；完整 Hub 可后置。

## 12. 分期交付

| Phase | 计划文件 | 可独立验收 |
|-------|----------|------------|
| **0 文档入口** | `docs/superpowers/plans/2026-08-10-document-ingress-anydoc.md` | 办公文档上传；文字档 AnyDoc；图片/扫描自动 Paddle |
| A 分层记忆 Kernel | `docs/superpowers/plans/2026-08-10-layered-memory-kernel.md` | L0–L3、预算召回、ACL 字段、API+测试 |
| A′ Outlines | （并入 C 前小任务或独立短计划） | `chat_structured` 覆盖 parser/workers |
| B 自进化资产 | `docs/superpowers/plans/2026-08-10-self-evolving-assets.md` | Distill、分级生效、Skill/Wiki、待审 |
| C Agent 工具 | `docs/superpowers/plans/2026-08-10-agent-memory-tools.md` | Loadout、冲突工具、异步 distill |
| D 合同追问 | 待写 `...-contract-chat.md` | 多轮对话 + L0 历史 + 条款引用 |
| E LightRAG | 待写 `...-lightrag-wiki.md` | 开关可控的图检索；ACL 不绕权；可回退 |

## 13. 风险与约束

- 遵守现有栈：Python≥3.10、FastAPI、SQLAlchemy、SQLite、sentence-transformers；**已确认可加 `firecrawl-anydoc`**；Outlines / LightRAG 引入前仍须确认。
- LLM 必须经 `LLMGateway`；Prompt 在 `server/core/prompts/`。
- 日志不打印完整合同正文或 API Key。
- 法律内容自动上线有误判风险 → 分级生效 + 可回滚 + 待审。
- LightRAG 索引与抽实体成本高 → 默认关闭，仅 Wiki ingest / 追问路径按需启用。
- embedding / LightRAG / AnyDoc 失败必须降级，不阻断主分析（PDF 可回退 PyMuPDF+Paddle）。
- Agent 工作流与编码准则见根目录 `AGENTS.md`。

## 14. 测试策略

- 单元：分层写入/召回预算/置信度升降/去重。
- API：pending approve/reject/rollback。
- Agent：mock LLM，断言工具仅在冲突路径调用；无记忆时行为与现网一致。
- 迁移：旧 `is_active` 规则仍可被检索。
