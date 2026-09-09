<p align="center">
  <img src="asset/合同红绿灯-app-icon--ios-android-.svg" width="120" alt="合同红绿灯 App Icon" />
</p>

<h1 align="center">合同红绿灯 🚦</h1>

<p align="center">
  <strong>拍照上传合同，AI 帮你识别风险条款</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License" />
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="Python" />
  <img src="https://img.shields.io/badge/LLM-OpenAI%20Compatible-brightgreen" alt="LLM" />
</p>

<p align="center">
  🌐 <strong>官网</strong>：<a href="https://clause-light.pages.dev/">https://clause-light.pages.dev/</a>
</p>

---

> ⚠️ **项目状态**
>
> 本项目仍在**积极开发中**，部分功能尚未完善：
> - 📱 手机端 PWA 正在开发中，暂不可用
> - 🐛 其他功能可能存在 Bug
>
> 如果你遇到问题或有建议，欢迎提交 [Issue](https://github.com/tanzhijir-04/clause-light/issues)！

---

## 这是什么？

合同红绿灯是一个**合同风险审查工具**。你只需要上传合同（PDF 或图片），系统会自动：

- 📝 识别合同文字
- 🔍 逐条分析风险
- 🚦 用**红黄绿三色**标注风险等级
- 💡 给出通俗易懂的解释和修改建议

**数据全部保存在你的电脑上，不会上传到任何服务器。**

---

## 快速开始

### 环境要求

- **Python 3.10 或更高版本**（推荐 3.11）
- Windows / macOS / Linux 都可以

### 安装步骤

**1. 下载代码**

```bash
git clone https://github.com/tanzhijir-04/clause-light.git
cd clause-light
```

**2. 创建虚拟环境**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. 安装依赖**

```bash
pip install -r requirements.txt
```

**4. 配置 AI 模型**

编辑 `.env` 文件，填入你的 API Key：

```bash
# DeepSeek（推荐，便宜好用）
LLM_DEEPSEEK_API_KEY=你的API密钥
```

> 💡 没有 API Key？可以用本地 Ollama（免费），见下方 [高级配置](#高级配置)

**5. 启动服务**

```bash
python -m server.main
```

**6. 打开浏览器**

访问 http://localhost:8080

---

## 使用方法

1. 点击 **"上传合同"** 按钮
2. 选择合同文件（PDF / JPG / PNG）
3. 等待分析完成（首次会下载 AI 模型，约 2-5 分钟）
4. 查看分析结果：
   - 🔴 红色 = 高风险，需要重点关注
   - 🟡 黄色 = 中风险，建议修改
   - 🟢 绿色 = 安全，可以签署

---

## 功能特性

- ✅ **5 个维度分析**：权责对等、财务风险、知识产权、争议解决、通用风险
- ✅ **知识库**：内置法律知识库，支持自定义规则
- ✅ **原文标注**：在合同原文上高亮风险条款
- ✅ **修改建议**：给出具体的条款修改建议
- ✅ **数据同步**：支持 WebDAV / S3 同步到云端

---

## 高级配置

### 使用本地 Ollama（免费）

如果你不想用付费 API，可以用本地 Ollama：

1. 安装 [Ollama](https://ollama.com/)
2. 下载模型：`ollama pull qwen2.5:7b`
3. 编辑 `data/llm_config.json`：

```json
{
  "local": {
    "enabled": true,
    "models": {
      "classify": "qwen2.5:7b",
      "analyze": "qwen2.5:7b",
      "explain": "qwen2.5:7b"
    }
  }
}
```

### 预下载 Embedding 模型（可选）

首次分析会自动下载知识库模型（约 400MB）。如果你想提前下载：

```bash
python scripts/download_embedding.py
```

---

## 常见问题

**Q: 启动时报错 "No module named 'xxx'"？**
A: 确保已激活虚拟环境，然后重新运行 `pip install -r requirements.txt`

**Q: 分析很慢怎么办？**
A: 首次分析需要下载 AI 模型，后续会很快。也可以用本地 Ollama 加速。

**Q: 支持哪些合同类型？**
A: 租赁、劳动、装修、外包、借款、服务等常见合同类型。

---

## 未来计划

- 📱 **手机端**：React Native PWA，手机也能用
- 🤖 **更多 AI 模型**：支持通义千问、文心一言等
- 📊 **批量分析**：一次上传多个合同
- 🔌 **插件系统**：自定义分析维度
- 🌐 **多语言支持**：英文合同分析

---

## 技术栈

- 后端：Python + FastAPI + SQLAlchemy
- 前端：纯 HTML/CSS/JS（无框架）
- AI：OpenAI 兼容 API / Ollama
- 数据库：SQLite（本地开发）/ PostgreSQL 16（M0 Compose）

## ContractOps 2.0 M0

M0 将合同、不可变版本、持久任务、事务 Outbox、租户 API Key 和脱敏审计落到统一底座。SQLite 仍用于本地兼容开发；容器部署使用 PostgreSQL 16 和 Redis 7。Kafka 不属于 M0 运行依赖。

### Docker 启动与验收

```powershell
docker compose -f docker/docker-compose.yml up --build -d
docker compose -f docker/docker-compose.yml run --rm migrate
python scripts/verify_m0.py
python scripts/import_v1_sqlite.py --source data/clause_light.db --dry-run
```

验收脚本输出 JSON，检查迁移版本、PostgreSQL/Redis、重复请求副作用、Worker 任务状态和日志隐私。停止服务时保留 PostgreSQL 命名卷：

```powershell
docker compose -f docker/docker-compose.yml down
```

### v1 数据备份与回滚

正式导入前先复制 SQLite 源文件并保留 SHA-256；导入器默认只读源库，建议先执行 `--dry-run`。需要回到 v1 时，停止 M0 服务、恢复备份的 `data/clause_light.db`，再切换到 `main` 分支启动旧版服务：

```powershell
Copy-Item data/clause_light.db data/clause_light.db.bak
git switch main
python -m server.main
```

## M1-A 本地知识库摄取

M1-A 先使用本地 SQLite 完成法规和内部规则的结构化摄取、分块、来源引用与词法检索，不要求 Docker、PostgreSQL、Redis 或远端服务。当前只读取 `shared/laws/*.json` 和 `shared/rules/*.json`，不会自动导入 v1 历史合同数据。

先执行只读检查：

```powershell
python scripts/ingest_m1_sources.py --source-dir shared --dry-run
```

确认源文件计数和分块计数后，再对已经完成迁移的本地数据库执行正式摄取：

```powershell
alembic upgrade head
python scripts/ingest_m1_sources.py `
  --source-dir shared `
  --database-url sqlite+aiosqlite:///data/clause_light.db
```

源标签和主题标签是两个字段：`[法律法规]` / `[内部规则]` 标签表示证据来源，原 JSON 中的 `tags` 或 `trigger_keywords` 只用于主题检索。相同来源重复执行会跳过；来源内容变化会保留旧版本并停用旧版本，不会静默覆盖。

---

## 技术细节

> 以下内容面向开发者，普通用户可跳过。

### 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        手机端 PWA                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ 拍照 / 上传  │  │ WebSocket    │  │ AsyncStorage 本地缓存  │ │
│  │ HTML5 Camera │  │              │  │ 离线可用               │ │
│  └──────┬───────┘  └──────┬───────┘  └────────────────────────┘ │
└─────────┼─────────────────┼────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     电脑端 FastAPI 服务                           │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────┐ │
│  │  OCR 引擎   │    │ Agent 编排  │    │    LLM 网关          │ │
│  │ PaddleOCR   │───▶│ 三段式流水线│───▶│ DeepSeek / OpenAI    │ │
│  │ 文字识别    │    │ 风险分析    │    │ Ollama / 通义千问    │ │
│  └─────────────┘    └──────┬──────┘    └──────────────────────┘ │
│                            │                                    │
│  ┌─────────────┐    ┌──────▼──────┐    ┌──────────────────────┐ │
│  │  知识库     │    │  SQLite     │    │    同步引擎          │ │
│  │ 规则 + 法规 │◀──▶│  数据库     │    │ WebDAV / S3          │ │
│  └─────────────┘    └─────────────┘    └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈详解

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端框架 | Python 3.10+ / FastAPI | 高性能异步 Web 框架 |
| 数据库 | SQLite + SQLAlchemy ORM | 零配置，数据本地存储 |
| OCR | PaddleOCR-VL | 中文合同文字识别 |
| LLM 调用 | OpenAI SDK（兼容格式） | 统一网关，支持多家大模型 |
| 本地 LLM | Ollama | 可选，完全离线运行 |
| Embedding | sentence-transformers | 本地向量化，知识库语义检索 |
| 前端 | 纯 HTML / CSS / JavaScript | 无框架依赖，PWA 离线可用 |
| 同步 | WebDAV / S3 | 多设备数据同步 |

### 目录结构

```
clause-light/
├── server/                    # 电脑端后端
│   ├── main.py                # FastAPI 入口
│   ├── config.py              # 配置管理
│   ├── api/                   # API 路由层
│   │   ├── contracts.py       #   合同分析接口
│   │   ├── knowledge.py       #   知识库接口
│   │   └── sync.py            #   同步接口
│   ├── core/                  # 核心业务逻辑
│   │   ├── agent.py           #   Agent 流程编排
│   │   ├── ocr.py             #   OCR 封装
│   │   ├── llm.py             #   LLM 网关
│   │   ├── embedding.py       #   Embedding 服务
│   │   ├── knowledge.py       #   知识库引擎
│   │   └── workers/           #   三段式分析流水线
│   │       ├── parser.py      #     结构解析
│   │       ├── workers.py     #     并行风险评估
│   │       └── evaluator.py   #     聚合评分
│   ├── models/                # 数据模型
│   │   └── database.py        #   SQLAlchemy 模型
│   └── static/                # Web 管理面板前端
│       ├── index.html         #   主入口
│       ├── css/               #   样式
│       └── js/                #   JavaScript
│
├── mobile/                    # 手机端 React Native
│   ├── App.tsx                # 根组件
│   └── src/                   # 源码
│
├── shared/                    # 共享数据
│   ├── rules/                 #   知识库规则（JSON）
│   └── laws/                  #   法规条文（JSON）
│
├── asset/                     # Logo、图标等资源
├── data/                      # 运行时数据（gitignored）
├── scripts/                   # 工具脚本
├── docker/                    # Docker 配置
├── tests/                     # 测试
└── docs/                      # 文档
```

### 三段式 Agent 分析流水线

```
OCR 识别全文
      │
      ▼
Stage 1: 结构解析（LLM）
  全文 → 拆分为条款 → 识别合同类型
  输出: ClauseItem[]
      │
      ├──▶ 知识库检索（关键词 + 向量）
      │
      ▼
Stage 2: 并行风险评估（5 个 Worker）
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ 权责对等 │ │ 财务风险 │ │ 知识产权 │
  └──────────┘ └──────────┘ └──────────┘
  ┌──────────┐ ┌──────────┐
  │ 争议解决 │ │ 通用风险 │
  └──────────┘ └──────────┘
      │
      ▼
Stage 3: 聚合评分（LLM）
  合并所有维度 → 综合评分 → 生成建议
  输出: 0-100 分 + 签署建议
```

### 5 个分析维度

| 维度 | 名称 | 关注点 |
|------|------|--------|
| equity | 权责对等 | 双方义务是否对等，单方面条款 |
| financial | 财务风险 | 付款周期、违约金、赔偿上限 |
| ip | 知识产权 | IP 归属、保密义务、竞业限制 |
| dispute | 争议解决 | 管辖地、仲裁条款、举证责任 |
| general | 通用风险 | 不可抗力、合同变更、其他条款 |

### API 接口

所有 API 返回 JSON 格式。Swagger 文档：http://localhost:8080/docs

#### 合同接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/contracts/` | 获取合同列表 |
| `GET` | `/api/contracts/{id}` | 获取合同详情 |
| `POST` | `/api/contracts/analyze` | 上传并分析合同（SSE 流式返回） |
| `PUT` | `/api/contracts/{id}` | 更新合同信息 |
| `DELETE` | `/api/contracts/{id}` | 删除合同 |
| `POST` | `/api/contracts/{id}/feedback` | 提交条款反馈 |

#### 知识库接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/knowledge/rules` | 获取规则列表 |
| `POST` | `/api/knowledge/rules` | 创建新规则 |
| `PUT` | `/api/knowledge/rules/{id}` | 更新规则 |
| `DELETE` | `/api/knowledge/rules/{id}` | 删除规则 |
| `GET` | `/api/knowledge/stats` | 知识库统计 |
| `GET` | `/api/knowledge/laws` | 法规条文列表 |

#### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/settings/llm` | 获取 LLM 配置 |
| `PUT` | `/api/settings/llm` | 更新 LLM 配置 |
| `POST` | `/api/settings/llm/test` | 测试 LLM 连接 |
| `GET` | `/api/sync/config` | 获取同步配置 |
| `POST` | `/api/sync/push` | 推送到云端 |
| `POST` | `/api/sync/pull` | 从云端拉取 |

### 环境变量

```bash
# LLM 配置（至少配一个）
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_OPENAI_API_KEY=sk-xxx

# 本地 LLM（可选）
OLLAMA_ENDPOINT=http://localhost:11434

# 服务配置
HOST=0.0.0.0
PORT=8080
DEBUG=false

# OCR 配置
OCR_USE_GPU=false

# 同步配置（可选）
SYNC_ENABLED=false
WEBDAV_URL=
WEBDAV_USERNAME=
WEBDAV_PASSWORD=
```

### Docker 部署

```bash
cd docker
docker-compose up -d --build
```

---

## 许可证

[MIT License](LICENSE) — 自由使用、修改、分发。
