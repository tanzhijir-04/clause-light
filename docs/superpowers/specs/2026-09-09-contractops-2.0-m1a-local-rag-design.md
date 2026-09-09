# ContractOps 2.0 M1-A 本地 RAG 内核设计规格

**日期：** 2026-09-09
**状态：** 设计已确认，待规格审阅
**范围：** M1「签前智能审查与生产级 RAG」的本机可验证子阶段

## 1. 目标

在不依赖 Docker、远端 PostgreSQL、pgvector 或 Redis 的前提下，完成以下本地闭环：

```text
shared/laws/*.json、shared/rules/*.json
        ↓
知识摄取与幂等版本管理
        ↓
带来源位置的 KnowledgeChunk
        ↓
SQLite 关键词检索 + 可选本地 Embedding
        ↓
ACL 过滤、去重、排序、Token Budget
        ↓
ContextPackage + Citation
        ↓
冲突标记与固定评测指标
```

本阶段的结果必须能在当前电脑上独立开发、测试和演示，并为下周接入 PostgreSQL 全文检索、pgvector、RRF 和 Rerank 保持稳定的上层接口。

## 2. 范围与非目标

### 2.1 本阶段包含

- 仅摄取 `shared/laws/` 和 `shared/rules/`；
- 知识文档和 Chunk 的 SQLite 持久化；
- 来源标签、原文位置和内容哈希；
- 幂等摄取、源文件版本保留和坏文件拒绝；
- ACL 过滤、关键词检索、可选本地 Embedding 降级；
- Citation、ContextPackage 和冲突人工复核状态；
- 固定 RAG 评测集、Recall@K、MRR、重复数和 ACL 泄漏数；
- 本地单元测试、集成测试和测试报告。

### 2.2 本阶段不包含

- v1 SQLite 中的历史合同和分析结果；
- 直接修改 v1 的 `KnowledgeRule`、`LegalReference` 或旧 API；
- PostgreSQL、pgvector、Redis 的本机安装或远程连接；
- Cross-encoder Rerank、真实 RRF 和 Query Rewrite；
- ReviewRun、RiskFinding 和完整风险审查 API；
- 让模型自动裁决法规与规则之间的冲突。

## 3. 设计原则

1. **来源优先：** 每个检索结果都必须能回答“来自哪份文件、哪一条内容”。
2. **不静默覆盖：** 内容变化生成新版本，旧来源保留；冲突来源同时保留。
3. **先权限后排序：** ACL 过滤发生在召回分数计算前，避免检索结果泄漏。
4. **降级可见：** Embedding 不可用时继续提供关键词结果，但显式标记 `degraded_mode=lexical`。
5. **不伪造能力：** 本地关键词检索不冒充 pgvector、RRF 或 Rerank。
6. **上层接口稳定：** 下周只替换 Retriever 实现，不改变 ContextPackage 和 Citation 结构。

## 4. 模块边界

计划新增模块：

| 路径 | 职责 |
|---|---|
| `server/modules/rag/models.py` | `KnowledgeDocument`、`KnowledgeChunk` 数据模型 |
| `server/modules/rag/schemas.py` | `RetrievalContext`、`RetrievalHit`、`Citation`、`ContextPackage` |
| `server/modules/rag/repository.py` | 文档、Chunk 的查询和幂等写入 |
| `server/modules/rag/chunking.py` | 规范化文本、边界感知分块、来源位置计算 |
| `server/modules/rag/ingest.py` | 法规/规则 JSON 校验、版本化摄取 |
| `server/modules/rag/retriever.py` | SQLite 关键词检索和可选 Embedding 评分 |
| `server/modules/rag/conflicts.py` | 来源优先级和冲突标记 |
| `server/modules/rag/evaluation.py` | 固定评测集和 Recall/MRR 指标 |
| `scripts/ingest_m1_sources.py` | 本地摄取与 dry-run 命令入口 |

旧的 `server/core/knowledge.py` 保持兼容，不直接重写现有 v1 检索逻辑。M1-A 通过新的 `rag` 模块使用 M0 的 `Base` 和数据库 session。

## 5. 数据模型

### 5.1 KnowledgeDocument

字段：

- `id`：UUID 主键；
- `organization_id`：公共法规/规则为空，为未来企业知识预留租户边界；
- `source_type`：`law` 或 `rule`；
- `source_key`：源文件相对路径，例如 `shared/laws/civil_code.json`；
- `source_title`：例如“中华人民共和国民法典”；
- `content_sha256`：规范化源内容哈希；
- `source_url`：法规原始链接，规则文件可为空；
- `status`：`active` 或 `disabled`；
- `metadata_json`：有效日期、校验日期、文件级来源元数据；
- 创建和更新时间。

唯一性规则为 `source_key + content_sha256`。同一个源文件内容重复摄取时返回已有文档；内容变化时创建新文档，不修改旧文档正文。

### 5.2 KnowledgeChunk

字段：

- `id`：UUID 主键；
- `document_id`：所属 `KnowledgeDocument`；
- `ordinal`：文档内稳定顺序；
- `heading`：法规条款号或规则分类；
- `content`：规范化后的 Chunk 正文；
- `source_start`、`source_end`：规范化文档坐标；
- `content_sha256`：Chunk 内容哈希；
- `embedding_json`：本地 SQLite 兼容的可选向量；
- `embedding_model`：向量模型标识；
- `visibility` 和 `acl_json`：公共来源默认 `public`；
- Chunk 级 `metadata_json`。

### 5.3 来源标签

来源标签和主题标签分开保存：

- 来源字段：`source_type`、`source_key`、`source_title`、`source_ref`、`source_url`；
- 原 JSON 中的 `tags` 保存为 `topic_tags`，只辅助检索，不作为来源证明；
- `source_label` 由来源字段生成，用于 Citation 和界面展示。

示例：

```text
[法律法规] 中华人民共和国民法典｜第四百六十九条
[内部规则] shared/rules/rental.json｜租赁规则第 1 条
```

## 6. 摄取与分块

### 6.1 摄取规则

摄取器只读取指定本地目录，不联网抓取来源 URL。

- 法规记录要求 `law_name`、`content`，可选 `article_number`、`effective_date`、`verified_at`、`source_url`、`tags`；
- 规则记录要求 `category`、`rule_text`，可选 `trigger_keywords`、`confidence`、`source`；
- 规范化换行、空白和 Unicode 后计算 SHA-256；
- 文件级事务独立提交；一个文件有结构错误时整文件拒绝，不产生半份知识数据；
- 报错只记录文件路径、字段和错误类型，不记录完整正文；
- 重复运行必须是幂等的。

### 6.2 分块规则

- 法规条文和规则正文默认保持完整；
- 超过 800 个字符时，按句号、分号等边界拆分；
- 拆分时保留条款号或规则编号；
- 重叠区最多 80 个字符；
- 每个 Chunk 记录其在规范化文档中的起止位置；
- 不为本阶段新增中文分词依赖。

## 7. 检索接口与本地实现

上层只依赖以下概念接口：

```python
class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        context: RetrievalContext,
        top_k: int = 10,
        token_budget: int = 3000,
    ) -> ContextPackage:
        ...
```

`RetrievalContext` 至少包含 `organization_id`、允许的可见性和合同类型；`ContextPackage` 包含归一化查询、命中项、Citation、实际预算、检索模式和降级原因。

SQLite 后端的步骤：

1. 规范化查询；
2. 先执行 `organization_id`、`visibility`、`acl_json` 和 `status` 过滤；
3. 对标题、条款号、来源主题标签和正文进行关键词评分；
4. 如果已有本地 Embedding 模型，叠加余弦相似度；
5. 按分数排序并按 Chunk 内容哈希去重；
6. 在 Token Budget 内加入完整 Chunk；
7. 为每个命中生成 Citation；
8. 返回 `degraded_mode="lexical"` 或 `degraded_mode="local_embedding"`。

下周的 PostgreSQL 后端复用同一接口，再增加全文检索、pgvector、RRF 和 Rerank，不把本地 JSON 向量格式当作生产索引格式。

## 8. Citation 与冲突处理

### 8.1 Citation 校验

Citation 必须包含：

- Chunk ID；
- `source_label`；
- 源文件；
- 条款号或规则编号；
- 起止位置；
- 内容 SHA-256。

如果 Chunk 不存在、位置越界或哈希不一致，则丢弃该命中，并将 ContextPackage 标记为需要复核。

### 8.2 来源冲突

两个文件观点冲突时：

- 两个来源都保留；
- 不静默覆盖或合并；
- 适用范围/地区匹配优先；
- 当前有效版本优先；
- 法律法规优先于官方解释、企业制度和内部经验规则；
- 同级别且无法判断时，同时返回并设置 `conflict_detected=true`；
- `requires_human_review=true` 时，后续风险结果不得伪装成“绿色/无需处理”。

M1-A 不使用模型自动判断复杂语义矛盾，只实现来源保留、优先级排序和人工复核标记。

## 9. 失败、权限与隐私

- ACL 过滤必须在排序前完成；
- 公共法规/规则使用 `organization_id=NULL` 和 `visibility=public`；
- 未来企业知识必须携带租户和 ACL 信息；
- Embedding 缺失不阻止正文入库；
- 日志不记录完整法规正文、查询上下文全文或凭据；
- 摄取失败可按源文件重试；
- 不修改 v1 SQLite 源库，不把历史合同作为本阶段输入。

## 10. 评测与测试

测试全部使用 SQLite 内存数据库，固定评测集只引用本地法规和规则来源。

必须覆盖：

- 7 个源文件的成功摄取；
- 重复摄取不重复写入；
- 文件内容变化保留旧版本并创建新版本；
- 来源标签、条款号、位置和哈希正确；
- Embedding 不可用时关键词降级；
- ACL 过滤和跨租户拒绝；
- Token Budget 不截断完整 Chunk；
- Citation 校验失败时进入复核；
- 冲突来源同时保留并标记人工复核；
- 评测输出 Recall@5、Recall@10、MRR@10、重复数和 ACL 泄漏数。

下周真实服务验收入口：

- PostgreSQL `alembic upgrade head`；
- PostgreSQL 全文/pgvector 检索；
- Redis 缓存和进度广播；
- RRF、Rerank 前后指标和 P95 延迟；
- M0/M1 端到端冒烟。

## 11. 验收标准

M1-A 只有同时满足以下条件才算完成：

1. 本地源文件可重复摄取且无重复数据；
2. 每个命中结果都有可校验的来源标签和 Citation；
3. ACL 过滤在召回排序前生效；
4. Embedding 不可用时仍能完成可见的关键词降级；
5. 来源冲突不会被静默覆盖，且能触发人工复核；
6. 固定评测命令可重复生成 Recall/MRR 和安全指标；
7. 原有 v1 测试全部通过；
8. 新增 M1-A 测试和测试报告保存到专门目录；
9. 下周 PostgreSQL/pgvector 实现只需替换检索后端，不改变上层结果结构。
