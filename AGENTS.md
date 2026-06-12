# AGENTS.md — ClauseLight 项目配置

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
- **Embedding**：sentence-transformers（本地运行）
- **LLM 调用**：openai SDK（兼容 OpenAI/DeepSeek/通义千问等 OpenAI 格式 API）
- **本地 LLM**：Ollama（通过 OpenAI 兼容接口调用）
- **文件处理**：PyMuPDF（PDF）、Pillow（图片）
- **同步**：webdavclient3（WebDAV）、boto3（S3）
- **WebSocket**：FastAPI 原生 WebSocket + python-socketio
- **前端管理面板**：纯 HTML + CSS + JS，无框架

### 手机端（PWA）
- **应用形态**：PWA（渐进式 Web 应用）
- **前端**：纯 HTML + CSS + JS，无框架
- **OCR**：不本地运行，发送给电脑端或云端
- **Embedding**：Transformers.js + ONNX（浏览器内运行）
- **本地存储**：IndexedDB
- **通信**：WebSocket（Socket.IO 客户端）
- **UI 风格**：移动端优先、简洁、红黄绿色彩编码

### 共享
- **规则库**：JSON 文件（shared/rules/）
- **法规库**：JSON 文件（shared/laws/）

## 目录结构

```
clause-light/
├── AGENTS.md              # 本文件
├── AGENT.md               # Agent 行为规范
├── PRD-ClauseLight.md     # 产品需求文档
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
│   │   └── ws.py          # WebSocket 接口
│   ├── core/              # 核心逻辑
│   │   ├── agent.py       # Agent Harness（流程编排）
│   │   ├── ocr.py         # PaddleOCR 封装
│   │   ├── llm.py         # LLM 网关（多模型路由）
│   │   ├── embedding.py   # Embedding 服务
│   │   ├── knowledge.py   # 知识库引擎
│   │   └── prompts/       # Prompt 模板
│   │       ├── classify.py
│   │       ├── split.py
│   │       ├── analyze.py
│   │       ├── suggest.py
│   │       └── score.py
│   ├── models/            # 数据模型
│   │   └── database.py    # SQLAlchemy 模型 + SQLite
│   ├── sync/              # 同步引擎
│   │   ├── webdav.py
│   │   ├── git_sync.py
│   │   └── s3_sync.py
│   └── static/            # Web 管理面板
│       ├── index.html
│       ├── css/style.css
│       ├── js/app.js
│       └── pages/
│
├── mobile/                # 手机端 PWA
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   ├── js/ocr.js          # OCR 通信
│   ├── js/agent.js        # Agent Harness（手机端精简版）
│   ├── manifest.json
│   └── sw.js
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
│   └── import_rules.py
│
├── docker/                # Docker 配置
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── docs/                  # 文档
    ├── TECHNICAL.md
    ├── CONTRIBUTING.md
    └── API.md
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
