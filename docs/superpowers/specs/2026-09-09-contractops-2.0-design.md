# ClauseLight ContractOps 2.0 设计规格

**状态：** 已确认，可进入分模块实施计划
**目标分支：** `dev/2.0`
**产品定位：** 面向企业法务、采购、销售和履约团队的通用合同智能底座
**实施方式：** 在 ClauseLight 现有仓库内演进，按模块交付，不另起产品仓库

## 1. 为什么做 2.0

ClauseLight v1 已经证明了从文档进入、OCR/解析、知识检索到多阶段风险审查和结果展示的完整闭环，但它仍以本地单用户审查工具为中心。2.0 要把这些能力沉淀为可复用、可审计、可扩展的企业合同智能底座，并补齐招聘岗位反复要求的生产工程能力：PostgreSQL、Redis、混合检索、Rerank、持久化 Agent、模型成本、可观测、权限、CI/CD 和量化评测。

2.0 不追求一次性重写全部功能。每个模块都必须形成一个可以独立演示、独立测试、失败可回滚的产品增量。

## 2. 目标用户与核心任务

| 角色 | 主要任务 | 2.0 提供的价值 |
| --- | --- | --- |
| 法务 | 审查条款、确认依据、维护规则、处理例外 | 有证据的风险结论、规则版本和完整审计轨迹 |
| 采购 | 发起合同、比较版本、跟踪供应商义务 | 标准化签前审查、差异定位、履约提醒 |
| 销售 | 快速定位不可接受条款、推动审批和签署 | 可解释的谈判建议、审批状态和签署衔接 |
| 履约负责人 | 跟踪付款、交付、验收、续约和违约事件 | 从合同文本提取义务，并将事件映射到风险处置 |
| 管理者 | 查看风险、效率、成本和合规情况 | 跨合同指标、模型成本、审查质量和处理时效 |

## 3. 产品边界

### 3.1 本期必须具备

- 合同、合同版本、文件、条款和参与方拥有稳定标识。
- 所有分析、修订、审批、履约和风险事件可追溯到合同版本。
- Agent 长任务支持持久化状态、幂等、重试、取消、人工确认和失败恢复。
- 检索结果必须携带来源、版本、权限和引用位置。
- PostgreSQL 保存业务事实；Redis 只承担可重建的加速状态。
- Kafka 只在跨系统履约事件达到独立扩展需求后启用，不能成为 M0 的启动依赖。
- LLM 调用统一经过网关，记录模型、Token、延迟、成功状态和估算成本，不记录完整合同正文。
- 所有模块提供自动化测试、迁移脚本、运行文档和可量化验收结果。

### 3.2 明确不做

- 不训练基础模型，不把模型训练当成产品壁垒。
- 不在 M0 引入微服务拆分、Kubernetes 或 Kafka 集群。
- 不把 Redis 当作合同、任务或审计记录的唯一存储。
- 不为匹配岗位关键词而强行用 LangChain、Dify 或多 Agent；技术选型必须有可验证收益。
- 不在没有业务事件和消费者的情况下提前实现复杂事件平台。
- 不在 2.0 首批模块接入真实电子签厂商；M3 先定义适配器和模拟实现。

## 4. 总体架构

2.0 采用模块化单体。API、后台 Worker 和迁移工具共享一套领域模块和 PostgreSQL 数据库，但以进程边界隔离在线请求与长任务。模块之间通过应用服务和领域事件协作，不直接修改其他模块的表。

```text
Browser / Mobile / External Systems
                 |
          FastAPI /api/v2
                 |
   +-------------+------------------------------+
   | contracts | review | negotiation | approval|
   | obligation| risk   | governance  | audit   |
   +-------------+------------------------------+
                 |
      PostgreSQL source of truth
       | jobs | checkpoints | outbox |
                 |
       Background worker processes
          |              |
   LLM/RAG gateway   Redis acceleration
                          |
                cache / rate limit / progress

M5 开始：Outbox Relay -> Kafka -> 履约事件消费者
```

### 4.1 数据职责

| 存储 | 保存内容 | 不保存内容 |
| --- | --- | --- |
| PostgreSQL | 租户、用户、合同、版本、条款、任务、检查点、审计、Outbox、评测结果 | 无 |
| pgvector | 知识块和合同授权片段的向量索引 | 不能脱离 PostgreSQL ACL 独立召回 |
| Redis | 缓存、限流计数、短期进度、发布订阅、幂等热点 | 合同正文、最终任务状态、唯一审计记录 |
| 对象存储 | 原始文件和派生文件 | 结构化业务状态 |
| Kafka | M5 起承载跨系统事件流 | 不能替代 Outbox 和业务数据库 |

### 4.2 兼容与迁移

- 新接口统一使用 `/api/v2`。
- v1 数据库不做原地升级；提供只读、幂等的一次性导入器，将 SQLite 内容写入 2.0 PostgreSQL。
- 导入器必须支持 `--dry-run`、源文件 SHA-256、逐表计数、ID 映射和重复执行保护。
- v1 页面和接口在 M0/M1 开发期间保留；M1 验收后再决定默认入口切换，不在 M0 删除旧代码。

## 5. 关键领域对象

### 5.1 M0 固定对象

- `Organization`：企业租户。
- `User`、`Membership`、`ApiCredential`：身份、成员关系和服务凭据。
- `Contract`：跨版本合同主记录。
- `ContractVersion`：不可变的合同文本版本。
- `ContractParty`：版本级合同主体、角色和标准化名称。
- `Clause`：拥有稳定位置和内容摘要的版本级条款。
- `DocumentAsset`：原始文件及其内容摘要、对象存储位置和解析状态。
- `ProcessingJob`、`JobStep`：长任务与检查点。
- `OutboxEvent`：与业务事务同提交的待发布事件。
- `AuditEvent`：不可变审计事件。
- `ImportBatch`、`LegacyIdMap`：v1 导入批次和旧新 ID 映射。

### 5.2 各模块新增对象

| 模块 | 新增核心对象 |
| --- | --- |
| M1 签前审查 | `KnowledgeDocument`、`KnowledgeChunk`、`RetrievalRun`、`ReviewRun`、`RiskFinding`、`Citation`、`EvalCase` |
| M2 谈判修订 | `NegotiationMatter`、`RevisionProposal`、`ClauseDiff`、`CommentThread` |
| M3 审批签署 | `ApprovalFlow`、`ApprovalStep`、`Decision`、`SignatureEnvelope` |
| M4 履约义务 | `Obligation`、`Milestone`、`EvidenceItem`、`ObligationStatusChange` |
| M5 事件风险 | `LifecycleEvent`、`RiskSignal`、`PlaybookRun`、`IntegrationOffset` |
| M6 续约终止 | `RenewalWindow`、`TerminationOption`、`NoticeAction` |
| M7 企业治理 | `PolicySet`、`RoleBinding`、`RetentionPolicy`、`Connector` |

## 6. Agent 和 RAG 边界

### 6.1 Agent

Agent 负责需要规划、工具协作和恢复的复杂任务；确定性校验、数据库更新和权限判断继续使用普通服务。Agent 状态必须落在 `ProcessingJob`/`JobStep`，工具调用必须声明输入输出 schema、超时、重试策略和副作用等级。

需要人工确认的动作包括：对外发送通知、修改合同状态、执行审批决定、触发签署、确认高风险义务和采用自动生成的条款修订。

### 6.2 RAG

M1 采用可测量的检索链：

```text
Query 归一化/改写
        |
PostgreSQL 全文检索 + pgvector 向量检索
        |
Reciprocal Rank Fusion
        |
Cross-encoder Rerank
        |
ACL 过滤、去重、排序、Token Budget
        |
带来源位置的 Context Package
        |
LLM 结构化风险结论 + Citation 校验
```

LightRAG 保留为图检索实验适配器，只有在离线评测中对跨文档、多跳法规问题产生稳定增益时才进入默认链路。

## 7. Redis 与 Kafka 决策

### 7.1 Redis

Redis 在 M0 后半段接入，承担：

- 租户/API 凭据级限流；
- 检索和配置的短时缓存；
- WebSocket/SSE 的任务进度广播；
- 可重建的幂等热点和分布式互斥。

Redis 不替换 PostgreSQL 的任务表、Outbox、审计表、合同表或评测表。开发环境允许关闭 Redis 并使用进程内降级；生产配置要求 Redis 健康，否则启动失败。

### 7.2 Kafka

Kafka 从 M5 开始接入。M0 只定义事件信封和 Outbox；M2–M4 只向 Outbox 写领域事件。M5 增加 Relay、Schema Compatibility、Consumer Idempotency 和 Dead Letter 流程。这个顺序保证没有 Kafka 时 M0–M4 仍能完整运行。

## 8. 稳定性、安全与隐私

- 默认不在日志、Trace、指标或异常消息中记录完整合同正文。
- 对象存储路径必须按租户隔离；下载使用短时签名 URL。
- 所有查询同时携带 `organization_id`，数据库层提供防遗漏约束和仓储测试。
- API 凭据只保存带 Pepper 的摘要和可展示前缀。
- 任务必须具备幂等键；重试不得重复创建合同版本或重复发布事件。
- Outbox 消费者使用事件 ID 去重；Kafka 消费者在本地事务完成后提交 Offset。
- OCR、解析、Embedding、Rerank 和 LLM 均设置超时与可观测的降级路径。
- 当前 PaddleOCR 3.x 与 v1 构造参数不兼容；M0 固定兼容版本并加入真实图片冒烟测试。

## 9. 量化验收体系

| 维度 | 指标 |
| --- | --- |
| 检索 | Recall@5、Recall@10、MRR@10、Rerank 前后增益、ACL 泄漏数 |
| 生成 | 引用正确率、无依据结论率、结构化输出成功率、人工复核捕获率 |
| Agent | 任务成功率、恢复成功率、重复副作用数、人工接管率 |
| 性能 | API P95、检索 P95、单合同端到端时延、Worker 吞吐 |
| 成本 | 单合同输入/输出 Token、单合同估算成本、模型路由节省比例 |
| 产品 | 审查完成时长、风险确认率、修订采纳率、逾期义务发现率 |

所有对外展示的提升数字必须由固定数据集、固定模型/价格快照和可重复命令生成，不能手写宣传数字。

## 10. 模块顺序与发布门

| 顺序 | 模块 | 发布门 |
| --- | --- | --- |
| M0 | 合同智能底座 | PostgreSQL、迁移、租户、任务、Outbox、Redis、可观测、OCR、CI 全部通过 |
| M1 | 签前智能审查/RAG | 混合检索与 Rerank 有离线基准，风险结论均可追溯到引用 |
| M2 | 谈判与修订 | 版本差异、建议和人工采纳形成审计闭环 |
| M3 | 审批与签署 | 审批状态机可恢复，外部签署通过适配器隔离 |
| M4 | 履约义务 | 义务、期限、责任方、证据均可回溯到合同版本和条款 |
| M5 | 履约事件与风险处置 | Kafka 事件契约、幂等消费、重放和 DLQ 经故障注入验证 |
| M6 | 续约与终止 | 续约窗口和通知动作可审计、可人工确认 |
| M7 | 企业治理与集成 | RBAC、保留策略、连接器与组织级指标完成 |

## 11. 求职证据映射

2.0 不是技术栈陈列。每个模块必须同时产出三类证据：

1. **可运行证据：** Docker Compose、一条命令启动、演示数据和端到端测试。
2. **选型证据：** ADR 说明为什么选择 PostgreSQL、Redis、Kafka、自研工作流或框架。
3. **结果证据：** 固定实验命令生成性能、质量、稳定性和成本指标。

完成 M0+M1 后即可重点证明 Python/FastAPI、PostgreSQL、Redis、复杂 RAG、Agent 恢复、LLM Gateway、成本监控、Docker/CI/CD 和生产工程能力。Kafka、审批、履约和治理用于继续强化企业场景，不应阻塞第一版求职成果。
