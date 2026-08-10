# AGENTS.md — ClauseLight 项目配置

## 项目概述

ClauseLight（合同红绿灯）是一个开源合同风险审查工具。
用户拍照上传合同，系统自动识别文字、逐条分析风险、给出通俗解释和修改建议。
内置可自进化的法律知识库与分层记忆，由 Pipeline + 有限工具的 Agent 驱动分析；数据默认本地存储。

更细的行为边界见 [`AGENT.md`](./AGENT.md)；记忆/知识架构见 [`docs/superpowers/specs/2026-08-10-self-evolving-memory-design.md`](./docs/superpowers/specs/2026-08-10-self-evolving-memory-design.md)。

## 技术栈

### 电脑端（后端服务）
- **语言**：Python >= 3.10
- **Web 框架**：FastAPI + uvicorn
- **数据库**：SQLite（通过 SQLAlchemy ORM）
- **OCR**：PaddleOCR（图片 / 扫描件自动调用）
- **文档解析**：Firecrawl AnyDoc（`firecrawl-anydoc`）— Word/Excel/PPT/ODF/RTF/EPUB/CSV/文字 PDF → Markdown
- **Embedding**：sentence-transformers
- **LLM 调用**：openai SDK（兼容 OpenAI/DeepSeek/通义千问等 OpenAI 格式 API）
- **结构化输出**：Outlines（.txt）经 `LLMGateway.chat_structured` 统一接入；失败回退 `parse_json` + Pydantic 校验
- **图检索（规划中）**：HKUDS/LightRAG 作为 Wiki/法规双层检索后端，默认可选、本地可关
- **本地 LLM**：Ollama（通过 OpenAI 兼容接口调用）
- **文件处理**：AnyDoc + Pillow；扫描 PDF 转图仍可用 PyMuPDF
- **同步**：webdavclient3（WebDAV）、boto3（S3）
- **WebSocket**：FastAPI 原生 WebSocket
- **前端管理面板**：纯 HTML + CSS + JS，无框架

### 手机端（React Native）
- **应用形态**：React Native（Expo managed workflow）
- **前端**：React Native + TypeScript
- **OCR / Embedding**：不本地运行，调用电脑端
- **本地存储**：AsyncStorage
- **通信**：WebSocket + HTTP API
- **UI 风格**：移动端优先、简洁、红黄绿色彩编码

### 共享
- **规则库**：JSON 文件（`shared/rules/`）
- **法规库**：JSON 文件（`shared/laws/`）

## 目录结构

```
clause-light/
├── AGENTS.md              # 本文件（项目配置 + Agent 工作流）
├── AGENT.md               # Agent 行为边界（技术栈/安全硬约束）
├── README.md
├── requirements.txt
├── server/                # 电脑端后端
│   ├── main.py
│   ├── config.py
│   ├── api/               # contracts / knowledge / memory / ws ...
│   ├── core/              # agent / ocr / llm / knowledge / memory / distill ...
│   ├── models/database.py
│   └── static/            # 纯 HTML/CSS/JS 管理面板
├── mobile/                # React Native（Expo）
├── shared/rules|laws/
├── data/                  # gitignored 运行时数据
├── scripts/
├── tests/
└── docs/
    └── superpowers/
        ├── specs/         # 设计规格
        └── plans/         # 实施计划
```

## Agent 工作流程

接到任务后**必须**按以下顺序执行：

1. **探索**：先读相关文件与规格，禁止凭文件名猜测内容
2. **澄清**：需求模糊，或涉及**新增配置 / 新增依赖 / 改表结构 / 改已有 API 签名**时，**先反问**
3. **计划**：变更超过 3 个文件时，先输出修改计划再动手
4. **实现**：按 Task/模块小步落地；**每完成一个模块立即 commit**
5. **验证**：跑测试 / lint（若有），输出结果摘要
6. **总结**：列出本次变更的文件清单与影响范围

与 [`AGENT.md`](./AGENT.md) 冲突时：**硬边界以 AGENT.md 为准**；工作流与编码准则以本文件为准。

## 编码行为准则

**权衡：** 以下准则偏向谨慎而非速度。对简单任务，请自行判断。

### 1. 先思考再编码

**不要假设。不要隐藏困惑。明确权衡。**

实现前：
- 明确陈述你的假设；不确定时，先问
- 存在多种理解时，列出来——不要默默选一种
- 有更简单方案时，说出来；必要时提出反对
- 不清楚时停下来，说明哪里困惑，先问

### 2. 简单优先

**用最少代码解决问题。不做推测性扩展。**

- 不添加未要求的功能
- 不为一次性代码做抽象
- 不添加未要求的「灵活性」或「可配置性」
- 不为不可能的场景写错误处理
- 写了 200 行能 50 行搞定，就重写

自问：「资深工程师会觉得这过度复杂吗？」如果是，就简化。

### 3. 精准改动

**只动必须动的。只清理自己造成的遗留。**

编辑现有代码时：
- 不要「顺手」改相邻代码、注释或格式
- 不要重构没坏的东西
- 匹配现有风格，即使你个人偏好不同
- 发现无关死代码，提及即可——不要删除

你的改动造成无用 import/变量/函数时：
- 删除**你的改动**导致的无用项
- 不要删除改动前就存在的死代码，除非用户要求

检验标准：每一行改动都应能直接追溯到用户请求。

### 4. 目标驱动执行

**定义成功标准。循环验证直到达成。**

把任务转化为可验证目标：
- 「加校验」→ 「为无效输入写测试，再让它们通过」
- 「修 bug」→ 「写复现测试，再让它通过」
- 「重构 X」→ 「重构前后测试都通过」

多步任务时，简要列出计划：

```
1. [步骤] → 验证：[检查项]
2. [步骤] → 验证：[检查项]
3. [步骤] → 验证：[检查项]
```

清晰的成功标准让你能独立循环；模糊标准（「让它能跑」）会不断需要澄清。

**这些准则生效的标志：** diff 里不必要的改动更少、因过度复杂而重写的次数更少、澄清问题出现在实现之前而非犯错之后。

## 实现原则

1. **简单优先**：能用现成库就不自己写；先问再加依赖
2. **SQLite 优先**：不上 PostgreSQL，零配置（LightRAG 若需额外存储须可关、默认可本地降级）
3. **无框架前端**：纯 HTML/CSS/JS，不引入 React/Vue 等框架（手机端 RN 除外）
4. **本地优先**：数据默认不离开本地；同步 / 团队记忆 / LightRAG 云组件需用户主动开启
5. **渐进增强**：离线可用规则引擎兜底，有网络有 LLM 时体验更好
6. **错误降级**：每一步失败都有兜底方案，不会整体崩溃
7. **单文件启动**：`python -m server.main` 一条命令启动服务

## 开发约定

- 所有 Python 文件使用 type hints
- 所有 API 返回 JSON 格式
- 所有 LLM 调用通过 `server/core/llm.py` 统一网关（含未来 Outlines 结构化输出）
- 所有 prompt 模板存放在 `server/core/prompts/` 目录
- 所有数据库操作通过 SQLAlchemy，不写裸 SQL
- 所有前端代码无外部 CDN 依赖（桌面管理面板离线可用）
- 代码注释使用中文
- Git：每完成一个可独立验证的**模块/Task**就立即 `commit`（不要攒一大包）；仅在用户要求时创建额外整理性提交；**默认不 push**，除非用户明确要求推送
- Commit message 使用约定格式（用户规则）：`:emoji: ai-feat(类型) 简短说明`（类型：新增/新功能/修改/修复）；表情按 [gitmoji](https://gitmoji.js.org/)

## 记忆 / 知识 / 权限（摘要）

- 分层记忆 L0–L3；资产含规则、Skill、Wiki；进化：自动提炼 + 用户反馈
- 检索必须带权限上下文（`owner` / `visibility` / ACL）；无权限不得召回
- 图检索采用 **HKUDS/LightRAG**，挂在 Wiki/法规检索适配层，不取代 Memory Kernel
- 多用户与细粒度 ACL：表结构一期预留，UI/登录可后置
