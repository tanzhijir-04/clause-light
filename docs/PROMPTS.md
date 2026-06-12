# Claude Code 开发提示词集

以下所有提示词均可直接发送给 Claude Code 执行。
每个提示词对应一个独立的开发任务，严格按顺序执行。

---

## Phase 1: 基础设施

### 提示词 1.1 — 项目配置

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md 了解项目全貌。

然后实现 server/config.py，要求：
1. 使用 pydantic-settings 的 BaseSettings 类
2. 支持从 .env 文件和环境变量读取配置
3. 包含以下配置组：服务（HOST/PORT/DEBUG）、数据库（DATABASE_URL）、
   文件存储（UPLOAD_DIR/MAX_UPLOAD_SIZE）、
   LLM远程API（PROVIDERS字典，含deepseek/openai两个默认配置）、
   LLM本地Ollama（OLLAMA_ENDPOINT/OLLAMA_MODELS）、
   OCR（LANGUAGE/USE_GPU）、
   同步（SYNC_ENABLED/WEBDAV配置/S3配置）
4. LLM API Key 从环境变量读取（如 LLM_DEEPSEEK_API_KEY、LLM_OPENAI_API_KEY）
5. 提供 get_settings() 函数获取单例配置

同时创建 .env.example 文件列出所有环境变量。
同时创建 .gitignore 文件，排除 data/、__pycache__/、.env、*.pyc、.DS_Store。

完成后 git commit: "chore: 初始化项目配置和基础文件"
```

### 提示词 1.2 — 数据库模型

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/models/database.py，要求：
1. 使用 SQLAlchemy 2.0 async 风格（AsyncSession、create_async_engine）
2. 创建以下表（对应 PRD 中的数据表设计）：
   - contracts（合同主表）
   - analyses（分析结果表）
   - clause_analyses（条款分析表）
   - knowledge_rules（知识库规则表）
   - legal_references（法规条文表）
   - sync_log（同步日志表）
3. 每个表定义对应的 SQLAlchemy ORM 模型类
4. 提供 get_db() async generator 用于 FastAPI 依赖注入
5. 提供 init_db() 函数用于首次启动时创建表
6. 所有表使用 UUID 作为主键（uuid.uuid4().hex）
7. JSON 字段使用 Text 类型存储，代码层面做序列化/反序列化

同时更新 scripts/init_db.py：调用 init_db() 创建数据库表并输出确认信息。

完成后 git commit: "feat: 实现数据库模型和初始化脚本"
```

### 提示词 1.3 — LLM 网关

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/core/llm.py，要求：
1. 使用 openai SDK（兼容 OpenAI 格式 API）
2. 实现 LLMGateway 类：
   - __init__: 接收 Settings 配置
   - async chat(messages, task, temperature, max_retries) → LLMResponse
   - async chat_stream(messages, task, temperature) → AsyncGenerator[str]
3. LLMResponse 数据类：content, model, provider, tokens_used, latency_ms
4. task 参数决定使用哪个模型（classification/analysis/explanation/scoring）
5. 根据 Settings 中的 LLM_DEFAULT_PROVIDER 选择默认提供商
6. 故障切换：主模型失败 → 重试2次（换 temperature）→ 切换备用提供商
7. 自定义异常类：LLMError, LLMRateLimitError, LLMConnectionError, LLMFormatError
8. 所有 LLM 调用的 token 用量和延迟用 logging 记录
9. 添加响应缓存：相同输入（task+messages hash）5分钟内返回缓存结果（简单 dict 缓存即可）

同时创建 requirements.txt，包含：fastapi, uvicorn[standard], sqlalchemy[asyncio], aiosqlite,
pydantic-settings, openai, paddlepaddle, paddleocr, sentence-transformers,
PyMuPDF, Pillow, webdavclient3, boto3, python-socketio, python-multipart

完成后 git commit: "feat: 实现 LLM 统一网关"
```

### 提示词 1.4 — Prompt 模板框架

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/core/prompts/ 下的所有 prompt 模板文件。
每个文件是一个 Python 模块，包含 prompt 文本常量和生成函数。

1. prompts/classify.py
   - CLASSIFY_SYSTEM_PROMPT 常量
   - classify_prompt(contract_text: str) → list[dict] 函数
   - 要求 LLM 返回纯文本合同类型名称

2. prompts/split.py
   - SPLIT_SYSTEM_PROMPT 常量
   - split_prompt(full_text: str, contract_type: str) → list[dict] 函数
   - 要求 LLM 返回 JSON 数组 [{clause_number, title, content, level}]

3. prompts/analyze.py
   - ANALYZE_SYSTEM_PROMPT 常量
   - ANALYZE_USER_TEMPLATE 模板字符串
   - analyze_prompt(clause_content, contract_type, contract_context, kb_rules) → list[dict] 函数
   - 要求 LLM 返回 JSON {risk_level, risk_type, risk_summary, plain_explanation, legal_basis, severity_score}

4. prompts/suggest.py
   - SUGGEST_SYSTEM_PROMPT 常量
   - suggest_prompt(clause_content, risk_type, risk_summary) → list[dict] 函数
   - 要求 LLM 返回 JSON {suggested_clause, modification_reason, can_negotiate, negotiation_tip}

5. prompts/score.py
   - SCORE_SYSTEM_PROMPT 常量
   - score_prompt(all_analyses: list[dict]) → list[dict] 函数
   - 要求 LLM 返回 JSON {overall_score, risk_distribution, top_risks, one_line_summary, recommendation}

6. prompts/__init__.py
   - 导出所有模块的公共函数

所有 prompt 中文撰写，明确要求 JSON 输出格式，system prompt 包含角色定义和输出约束。

完成后 git commit: "feat: 实现全部 Prompt 模板"
```

---

## Phase 2: 核心引擎

### 提示词 2.1 — OCR 引擎

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/core/ocr.py，要求：
1. OCREngine 类：
   - __init__: 接收 use_gpu 和 lang 参数，初始化 PaddleOCR
   - async recognize(file_path: str) → OCRResult
2. 支持输入：JPG/PNG/HEIC 图片、PDF 文件
3. PDF 处理：用 PyMuPDF 逐页提取为图片，再分别 OCR
4. OCR 结果整合：拼接为全文，尝试识别条款层级结构
   - 用正则匹配条款编号（"第X条"、"X.X"、"X、"等模式）
   - 按条款编号拆分文本
5. 置信度过滤：低于 0.6 的文本块标记为"可能识别有误"
6. 数据类定义：OCRResult, PageResult, TextBlock, Clause
7. 异常处理：文件不存在、格式不支持、OCR 引擎初始化失败

注意：PaddleOCR 是同步阻塞调用，需要用 asyncio.to_thread() 包装。

完成后 git commit: "feat: 实现 PaddleOCR-VL OCR 引擎封装"
```

### 提示词 2.2 — Agent Harness

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/core/agent.py，这是系统的核心模块。

实现 ContractAgent 类：
1. __init__: 接收 LLMGateway, KnowledgeEngine, OCREngine 实例
2. async analyze(file_path, contract_type_hint, on_step) → AnalysisResult
   - on_step 是可选的进度回调 async callable(event_type, data)
3. 实现完整的 7 步流程：
   - Step 1: OCR（调用 ocr.recognize）
   - Step 2: 分类（调用 llm.chat + classify_prompt）
   - Step 3: 条款拆解（调用 llm.chat + split_prompt）
   - Step 4: 知识库检索（调用 knowledge.search，对每个条款检索）
   - Step 5: 逐条风险分析（并发调用 llm.chat + analyze_prompt，用 asyncio.gather）
   - Step 6: 修改建议（对红黄条款调用 llm.chat + suggest_prompt）
   - Step 7: 综合评分（调用 llm.chat + score_prompt）
4. 每步都有 _safe_step 包装：重试 + 降级 + 异常捕获
5. Step 5 并发限制：最多同时 5 个并发 LLM 请求（asyncio.Semaphore）
6. 定义数据类：AnalysisResult, ClauseAnalysis, Suggestion, FinalScore
7. 定义回调事件类型枚举：STEP_OCR, STEP_CLASSIFY, STEP_SPLIT, STEP_RETRIEVE, STEP_ANALYZE, STEP_SUGGEST, STEP_SCORE

完成后 git commit: "feat: 实现 Agent Harness 核心流程编排"
```

### 提示词 2.3 — 知识库引擎

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/core/knowledge.py，要求：
1. KnowledgeEngine 类：
   - __init__: 接收 AsyncSession 数据库会话和 embedding 模型名
   - 初始化 sentence-transformers 的 SentenceTransformer 模型
2. async search(query, contract_type, top_k=5) → list[Rule]
   - 关键词匹配（简单字符串包含）
   - 合同类型过滤（通用规则 + 对应类型规则）
   - Embedding 语义检索（计算 query 向量与规则向量的余弦相似度）
   - 三种结果合并去重，按置信度 × 相似度综合排序
   - 返回 Top K
3. async add_rule(rule: RuleCreate) → Rule
4. async update_rule(rule_id, rule_update) → Rule
5. async delete_rule(rule_id) → bool
6. async get_stats() → KnowledgeStats（规则总数、按类型分布、平均置信度等）
7. async update_from_feedback(clause_id, feedback) → None
   - correct: 对应规则 confirm_count + 1，confidence 提升
   - incorrect: 对应规则 reject_count + 1，confidence 降低
8. 规则缓存：首次加载后缓存在内存，增删改时刷新缓存

向量计算用 numpy 实现，不需要引入额外向量数据库。

完成后 git commit: "feat: 实现知识库引擎（检索 + 自进化）"
```

---

## Phase 3: API 层

### 提示词 3.1 — 合同分析 API

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/api/contracts.py，要求：
1. 使用 FastAPI APIRouter
2. POST /api/contracts/analyze
   - 接收：UploadFile（图片/PDF）+ 可选 contract_type 字段
   - 校验文件类型（只允许 jpg/png/pdf）
   - 保存文件到 UPLOAD_DIR
   - 调用 ContractAgent.analyze()
   - 保存分析结果到数据库
   - 返回完整分析结果 JSON
3. GET /api/contracts
   - 合同列表，支持分页（page/page_size）、搜索（q）、类型筛选（type）
   - 返回 {items: [...], total: int, page: int, page_size: int}
4. GET /api/contracts/{contract_id}
   - 合同详情 + 所有分析结果
5. POST /api/contracts/{contract_id}/feedback
   - 接收 {clause_analysis_id: str, feedback: "correct"|"incorrect"}
   - 调用 knowledge.update_from_feedback()
6. GET /api/contracts/{contract_id}/report
   - 生成 Markdown 格式的分析报告
   - Content-Type: text/markdown

每个接口都做完整的异常处理和参数校验。

完成后 git commit: "feat: 实现合同分析 API 接口"
```

### 提示词 3.2 — WebSocket 接口

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/api/ws.py，要求：
1. 使用 FastAPI WebSocket
2. 连接端点：ws://host:port/ws/client?token={client_token}
3. 支持两种客户端类型：
   - mobile：手机端，接收分析进度和结果
   - admin：管理面板，接收全局状态
4. 实现 ConnectionManager 类：
   - connect(websocket, client_type, client_id)
   - disconnect(websocket)
   - broadcast(client_type, event_type, data)
   - send_to(client_id, event_type, data)
5. 消息格式：{type: "event_name", data: {...}, timestamp: "..."}
6. 支持的事件类型：
   - analysis_progress：分析进度（step 完成通知）
   - analysis_result：分析结果（逐条推送）
   - analysis_error：分析失败
   - sync_status：同步状态更新
7. 手机端可发送消息触发分析（携带 file 信息或引用已上传的文件）

完成后 git commit: "feat: 实现 WebSocket 实时通信接口"
```

### 提示词 3.3 — FastAPI 主入口

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/main.py，要求：
1. 创建 FastAPI app 实例，title="ClauseLight"，version="0.1.0"
2. 注册所有路由：contracts, knowledge, ws
3. startup 事件：
   - 初始化数据库（init_db()）
   - 初始化 LLM 网关
   - 初始化 OCR 引擎
   - 初始化知识库引擎
   - 初始化 Agent
   - 将依赖注入到 app.state
4. 挂载静态文件：
   - /admin/ → server/static/（管理面板）
   - /mobile/ → mobile/（手机端 PWA）
5. 添加 CORS 中间件（允许所有来源，开发阶段）
6. 添加请求日志中间件
7. 根路径返回简单欢迎页
8. 启动 uvicorn（可配置 host/port）

同时创建 server/api/contracts.py 和 server/api/knowledge.py 的占位文件（空路由），
确保 main.py 可以正常启动。

完成后 git commit: "feat: 实现 FastAPI 主入口和路由注册"
```

---

## Phase 4: 前端

### 提示词 4.1 — 电脑端管理面板

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现电脑端 Web 管理面板，所有文件放在 server/static/ 目录下。

要求：
1. server/static/index.html — 单页应用主入口
2. server/static/css/style.css — 完整样式
3. server/static/js/app.js — 主逻辑（路由、数据请求、页面渲染）

页面包含：
1. 首页/仪表盘：
   - 最近分析列表（合同名、评分、风险分布、时间）
   - 快速上传入口（拖拽或点击上传）
   - 知识库概览（规则总数、类型分布）

2. 合同详情页：
   - 总览卡片（分数 + 风险分布 + 一句话总结）
   - 条款列表（红黄绿标签，点击展开）
   - 每条展开后：原文、通俗解释、修改建议

3. 知识库管理页：
   - 规则列表（按类型分组、搜索、筛选）
   - 新增/编辑规则表单
   - 规则审核列表（待审核的新规则）

4. 设置页：
   - LLM 配置（API Key 输入、模型选择、Ollama 地址）
   - 同步配置
   - 数据导出

设计风格：
- 简洁专业，白色背景，少量色彩
- 红黄绿作为风险等级主色
- 表格驱动，信息密度适中
- 响应式布局，支持手机访问管理面板

所有 API 调用使用 fetch()，不引入 axios 等外部库。
路由使用 hash 路由（#/contracts、#/knowledge、#/settings）。

完成后 git commit: "feat: 实现电脑端 Web 管理面板"
```

### 提示词 4.2 — 手机端 PWA

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现手机端 PWA，所有文件放在 mobile/ 目录下。

要求：
1. mobile/index.html — 单页应用
2. mobile/css/style.css — 移动端优先样式
3. mobile/js/app.js — 主逻辑（视图切换、API 调用）
4. mobile/js/ocr.js — OCR 通信模块
5. mobile/js/agent.js — 精简版 Agent Harness
6. mobile/manifest.json — PWA 配置
7. mobile/sw.js — Service Worker（离线缓存）

页面视图：
1. 首页：
   - 大按钮：拍照 / 选择文件
   - 连接状态指示器（已连接电脑 / 使用云端 API / 离线模式）
   - 最近分析列表（最近 5 条）

2. 分析中：
   - 进度条 + 当前步骤文字
   - 逐步出现的分析结果（流式显示）

3. 结果页：
   - 总览卡片（分数、红黄绿分布、一句话总结）
   - 条款列表（可折叠）
   - 每条：风险标签、通俗解释、修改建议（一键复制按钮）
   - 底部：反馈按钮（对/错）+ 重新分析 + 分享

4. 历史列表：
   - 所有历史分析记录

功能逻辑：
- mobile/js/agent.js 实现精简版 Agent：
  1. 拍照/选文件
  2. 检测连接状态（尝试连电脑 WebSocket）
  3. 如果连了电脑 → 发送给电脑端分析
  4. 如果没连电脑 → 发送给云端 API 直接分析（手机端调 LLM API）
  5. 接收结果并渲染
- 本地缓存使用 IndexedDB（最近 20 条分析记录）

设计风格：
- 移动端优先，大按钮、大字体
- 底部导航栏：首页 / 历史 / 设置
- 加载动画简洁
- 红黄绿色彩鲜明

完成后 git commit: "feat: 实现手机端 PWA"
```

---

## Phase 5: 知识库数据

### 提示词 5.1 — 基础规则库

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后创建知识库基础规则文件，放在 shared/rules/ 目录下。

创建以下 JSON 文件：

1. shared/rules/general.json — 通用合同风险规则（50+ 条）
   每条规则格式：
   {
     "id": "G001",
     "category": "通用",
     "rule_text": "规则描述",
     "trigger_keywords": ["关键词1", "关键词2"],
     "risk_level": "red",
     "risk_type": "风险类型",
     "explanation": "通俗解释",
     "legal_basis": "相关法律依据",
     "confidence": 0.9
   }

   覆盖的风险类型：
   - 违约金过高或不对等
   - 单方面免责条款
   - 放弃索赔权利
   - 模糊的交付标准
   - 不合理的竞业限制
   - 试用期过长
   - 知识产权归属不清
   - 争议解决条款不利
   - 自动续约陷阱
   - 保证金/押金风险
   - 等等

2. shared/rules/rental.json — 租赁合同专项（20+ 条）
   覆盖：押金退还、提前退租、维修责任、涨租条件、转租限制、房屋用途限制等

3. shared/rules/labor.json — 劳动合同专项（20+ 条）
   覆盖：竞业限制、加班条款、解除赔偿、试用期、社保缴纳、调岗条款等

4. shared/rules/renovation.json — 装修合同专项（15+ 条）
   覆盖：工期延误、增项费用、验收标准、保修期、材料规格、付款节点等

5. shared/rules/outsourcing.json — 外包合同专项（15+ 条）
   覆盖：交付标准、验收条件、付款节点、知识产权归属、保密条款、违约责任等

同时创建 scripts/import_rules.py：
- 读取所有 rules/*.json 文件
- 导入到数据库 knowledge_rules 表
- 跳过已存在的规则（按 id 去重）
- 输出导入统计

完成后 git commit: "feat: 创建基础规则库和导入脚本"
```

### 提示词 5.2 — 法规库

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后创建法规库基础文件，放在 shared/laws/ 目录下。

创建以下 JSON 文件：

1. shared/laws/civil_code.json — 民法典合同编相关条文
   格式：
   {
     "law_name": "中华人民共和国民法典",
     "articles": [
       {
         "number": "第四百九十六条",
         "content": "格式条款是当事人为重复使用而预先拟定...",
         "tags": ["格式条款", "霸王条款", "免责"]
       }
     ]
   }

   收录与合同风险最相关的条文（约30-50条），包括：
   - 合同的订立（格式条款、要约承诺）
   - 合同的效力（无效条款、可撤销）
   - 合同的履行（违约责任）
   - 合同的解除（法定解除、约定解除）
   - 违约责任（赔偿损失、违约金）

2. shared/laws/labor_law.json — 劳动合同法相关条文
   收录与劳动合同风险最相关的条文（约20-30条），包括：
   - 试用期规定
   - 竞业限制
   - 解除和终止
   - 经济补偿
   - 工作时间和休息休假

注意：条文内容以官方发布的最新版本为准，标注生效日期。

完成后 git commit: "feat: 创建法规库基础文件"
```

---

## Phase 6: 同步与完善

### 提示词 6.1 — 同步引擎

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现同步引擎，文件放在 server/sync/ 目录下。

1. server/sync/webdav.py — WebDAV 同步
   - WebDAVSync 类
   - async push(local_path, remote_path) → SyncResult
   - async pull(remote_path, local_path) → SyncResult
   - async test_connection() → bool
   - 使用 webdavclient3 库

2. server/sync/git_sync.py — Git 同步
   - GitSync 类
   - async commit_and_push(message) → SyncResult
   - async pull() → SyncResult
   - async status() → dict（当前 git 状态）
   - 使用 subprocess 调用 git 命令

3. server/sync/s3_sync.py — S3 兼容同步
   - S3Sync 类
   - async push(local_path, remote_path) → SyncResult
   - async pull(remote_path, local_path) → SyncResult
   - async test_connection() → bool
   - 使用 boto3 库

4. server/api/sync.py — 同步 API 路由
   - POST /api/sync/push — 手动推送
   - POST /api/sync/pull — 手动拉取
   - GET /api/sync/status — 同步状态
   - POST /api/sync/test — 测试连接
   - GET /api/sync/log — 同步历史

同时在 main.py 中注册 sync 路由。

完成后 git commit: "feat: 实现 WebDAV/Git/S3 同步引擎"
```

### 提示词 6.2 — 知识库 API

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后实现 server/api/knowledge.py，要求：
1. 使用 FastAPI APIRouter，前缀 /api/knowledge
2. GET /api/knowledge/rules
   - 规则列表，支持分页、按 category 筛选、按 keyword 搜索
3. POST /api/knowledge/rules
   - 新增规则，自动计算 embedding 向量
4. PUT /api/knowledge/rules/{rule_id}
   - 更新规则
5. DELETE /api/knowledge/rules/{rule_id}
   - 删除规则（软删除，设 is_active=false）
6. GET /api/knowledge/stats
   - 返回：总规则数、按类型分布、平均置信度、待审核数量
7. GET /api/knowledge/pending
   - 待审核的自动学习规则列表

完成后 git commit: "feat: 实现知识库管理 API"
```

### 提示词 6.3 — README 和文档

```
请先阅读 CLAUDE.md、AGENT.md 和 docs/TECHNICAL.md。

然后完善项目文档：

1. 更新 README.md，内容包含：
   - 项目名称和一句话介绍
   - 功能特性列表
   - 截图占位符
   - 快速开始（安装、配置、启动）
   - 手机访问方式
   - 配置说明（环境变量列表）
   - 技术栈说明
   - 项目结构说明
   - 贡献指南链接
   - MIT License 声明

2. 创建 docs/CONTRIBUTING.md：
   - 开发环境搭建
   - 代码规范
   - 提交规范（feat/fix/docs/refactor/test/chore）
   - 知识库规则贡献指南（JSON 格式、审核流程）
   - PR 流程

3. 创建 docs/API.md：
   - 所有 API 端点文档
   - 请求/响应示例
   - 错误码说明

完成后 git commit: "docs: 完善项目文档"
```

---

## 执行说明

1. 每个提示词都是独立的，可以按顺序逐个发送给 Claude Code
2. 每个提示词执行完后，确认代码可以运行再发送下一个
3. 如果某个步骤出错，修复后再继续
4. 每个步骤结束后会自动 git commit
5. 建议在发送每个提示词前，确保上一步的 commit 已完成
