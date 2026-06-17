# CLAUDE.md — ClauseLight 项目配置

## 项目概述

ClauseLight（合同红绿灯）是一个开源合同风险审查工具。
用户拍照上传合同，系统自动识别文字、逐条分析风险、给出通俗解释和修改建议。
内置可自进化的法律知识库，由专属 Agent 驱动分析引擎，数据全部本地存储。

## 技术栈

### 电脑端（后端服务）
- **语言**：Python >= 3.10
- **Web 框架**：FastAPI + uvicorn
- **数据库**：SQLite（通过 SQLAlchemy ORM）
- **OCR**：PaddleOCR-VL（paddlepaddle + paddleocr）
- **Embedding**：sentence-transformers（已声明依赖，embedding.py 待实现）
- **LLM 调用**：openai SDK（兼容 OpenAI/DeepSeek/通义千问等 OpenAI 格式 API）
- **本地 LLM**：Ollama（通过 OpenAI 兼容接口调用）
- **文件处理**：PyMuPDF（PDF）、Pillow（图片）
- **同步**：webdavclient3（WebDAV）、boto3（S3）（已声明依赖，sync/ 待实现）
- **WebSocket**：FastAPI 原生 WebSocket
- **前端管理面板**：纯 HTML + CSS + JS，无框架

### 手机端（React Native）
- **应用形态**：React Native（Expo managed workflow）
- **前端**：React Native + TypeScript
- **OCR**：不本地运行，发送给电脑端或云端
- **Embedding**：不本地运行，调用电脑端 API
- **本地存储**：AsyncStorage
- **通信**：WebSocket + HTTP API
- **UI 风格**：移动端优先、简洁、红黄绿色彩编码

### 共享
- **规则库**：JSON 文件（shared/rules/）
- **法规库**：JSON 文件（shared/laws/）

## 目录结构

```
clause-light/
├── CLAUDE.md              # 本文件
├── AGENT.md               # Agent 行为规范
├── PRD-ClauseLight.md     # 产品需求文档
├── PRD-annotated-view.md  # 原文标注视图 PRD
├── README.md
├── requirements.txt
├── pyproject.toml
├── .gitignore
│
├── server/                # 电脑端后端
│   ├── main.py            # FastAPI 入口
│   ├── config.py          # 配置管理
│   ├── api/               # API 路由
│   │   ├── contracts.py   # 合同分析接口
│   │   ├── knowledge.py   # 知识库接口
│   │   ├── sync.py        # 同步接口
│   │   ├── ws.py          # WebSocket 接口
│   │   ├── connection.py  # 手机端连接管理
│   │   └── models.py      # OCR 模型管理
│   ├── core/              # 核心逻辑
│   │   ├── agent.py       # Agent Harness（流程编排）
│   │   ├── ocr.py         # PaddleOCR 封装
│   │   ├── llm.py         # LLM 网关（多模型路由）
│   │   ├── knowledge.py   # 知识库引擎
│   │   ├── model_manager.py # OCR 模型下载管理
│   │   ├── prompts/       # Prompt 模板
│   │   │   ├── classify.py
│   │   │   ├── split.py
│   │   │   ├── analyze.py
│   │   │   ├── suggest.py
│   │   │   └── score.py
│   │   └── workers/       # 三段式分析流水线
│   │       ├── parser.py  # 阶段一：分类 + 条款拆分
│   │       ├── workers.py # 阶段二：五维度并行分析
│   │       └── evaluator.py # 阶段三：一致性校验 + 评分
│   ├── models/            # 数据模型
│   │   └── database.py    # SQLAlchemy 模型 + SQLite
│   ├── sync/              # 同步引擎（待实现）
│   │   └── __init__.py
│   └── static/            # Web 管理面板（纯 HTML/CSS/JS）
│       ├── index.html
│       ├── css/
│       │   ├── tokens.css
│       │   ├── base.css
│       │   ├── layout.css
│       │   ├── components.css
│       │   └── pages.css
│       ├── js/
│       │   ├── app.js
│       │   ├── router.js
│       │   ├── api.js
│       │   ├── components.js
│       │   ├── icons.js
│       │   ├── theme.js
│       │   └── pages/
│       └── pages/
│
├── mobile/                # 手机端 React Native（Expo）
│   ├── App.tsx            # 根组件
│   ├── app.json           # Expo 配置
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── screens/       # 页面组件
│       ├── components/    # 通用组件
│       ├── services/      # API/WebSocket 服务
│       ├── contexts/      # React Context
│       ├── navigation/    # 导航配置
│       ├── theme/         # 主题/颜色
│       ├── types/         # TypeScript 类型
│       └── utils/         # 工具函数
│
├── shared/                # 共享数据
│   ├── rules/             # 知识库规则（JSON）
│   │   ├── general.json
│   │   ├── rental.json
│   │   ├── labor.json
│   │   ├── renovation.json
│   │   └── outsourcing.json
│   └── laws/              # 法规条文（JSON）
│       ├── civil_code.json
│       └── labor_law.json
│
├── data/                  # 运行时数据（gitignored）
│   ├── clause_light.db
│   └── uploads/
│
├── scripts/               # 工具脚本
│   ├── init_db.py
│   ├── import_rules.py
│   ├── import_laws.py
│   └── backfill_ocr_text.py
│
├── docker/                # Docker 配置
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── docs/                  # 文档
│   ├── TECHNICAL.md
│   ├── CONTRIBUTING.md
│   ├── API.md
│   ├── AGENT_ARCHITECTURE.md
│   └── PROMPTS.md
│
├── tests/                 # 测试
│   ├── test_*.py          # 单元测试
│   ├── e2e_*.py           # E2E 测试
│   └── conftest.py
│
├── designs/               # UI 设计原型
│   ├── clause-light-desktop/
│   ├── clause-light-mobile/
│   └── contract-annotated-view/
│
├── asset/                 # 品牌资源（Logo、图标）
├── .env.example           # 环境变量示例
├── pytest.ini             # Pytest 配置
├── requirements.txt
├── pyproject.toml
├── CLAUDE.md              # 本文件
├── AGENTS.md              # 多 Agent 配置
├── AGENT.md               # Agent 行为规范
├── PRD-ClauseLight.md     # 产品需求文档
├── PRD-annotated-view.md  # 原文标注视图 PRD
└── README.md
```

## 实现原则

1. **简单优先**：能用现成库就不自己写，能用 Python 就不用其他语言
2. **SQLite 优先**：不上 PostgreSQL，零配置
3. **无框架前端**：纯 HTML/CSS/JS，不引入 React/Vue 等框架
4. **本地优先**：数据默认不离开本地，同步功能需用户主动开启
5. **渐进增强**：离线可用规则引擎兜底，有网络有 LLM 时体验更好
6. **错误降级**：每一步失败都有兜底方案，不会整体崩溃
7. **单文件启动**：`python server/main.py` 一条命令启动服务

## 开发约定

- 所有 Python 文件使用 type hints
- 所有 API 返回 JSON 格式
- 所有 LLM 调用通过 `server/core/llm.py` 统一网关
- 所有 prompt 模板存放在 `server/core/prompts/` 目录
- 所有数据库操作通过 SQLAlchemy，不写裸 SQL
- 所有前端代码无外部 CDN 依赖（PWA 离线可用）
- Git commit message 使用中文
- 代码注释使用中文
- **每次完成代码改动后，立即提交并推送到 GitHub，commit 不能为空，要写得很详细。**

