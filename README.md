# 合同红绿灯

> 拍照上传合同，红黄绿三色标注风险，告诉你哪些条款对你不利、建议怎么改。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)

## 功能特性

- **拍照即审** — 手机拍照或上传 PDF，自动识别合同文字
- **风险标注** — 红/黄/绿三色标注每条条款的风险等级
- **通俗解释** — 用大白话告诉你每条条款意味着什么
- **修改建议** — 给出具体的修改措辞，可一键复制
- **自进化知识库** — 使用越多越准，用户反馈自动优化规则
- **双端架构** — 电脑端全功能管理 + 手机端精简分析
- **本地优先** — 数据默认不离开你的设备
- **多 LLM 支持** — 支持 OpenAI、DeepSeek、Ollama 本地模型等

## 快速开始

### 方式一：本地安装（推荐开发）

#### 1. 克隆项目

```bash
git clone https://github.com/tanzhijir-04/clause-light.git
cd clause-light
```

#### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env，填入你的 LLM API Key（至少配一个）
```

#### 5. 启动服务

```bash
# 方式 A：一条命令启动（推荐）
python server/main.py

# 方式 B：使用 uvicorn 启动
python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

#### 6. 访问

- **管理面板**：http://localhost:8080/admin/
- **手机端**：手机浏览器访问 http://你的电脑IP:8080/mobile/
- **API 文档**：http://localhost:8080/docs

---

### 方式二：Docker 部署（推荐生产）

#### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

#### 2. 启动容器

```bash
cd docker

# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 3. 访问

- **管理面板**：http://localhost:8080/admin/
- **手机端**：手机浏览器访问 http://你的电脑IP:8080/mobile/

---

## 配置说明

在 `.env` 文件中配置以下环境变量：

```bash
# === LLM 配置（至少配一个）===

# DeepSeek（推荐，便宜）
LLM_DEEPSEEK_API_KEY=sk-xxx

# OpenAI
LLM_OPENAI_API_KEY=sk-xxx

# 通义千问
LLM_QWEN_API_KEY=sk-xxx

# === 本地 LLM（可选，需要先安装 Ollama）===
OLLAMA_ENDPOINT=http://localhost:11434

# === 服务配置 ===
HOST=0.0.0.0
PORT=8080
DEBUG=false

# === OCR ===
OCR_USE_GPU=false

# === 同步（可选，配置后可多设备同步）===
SYNC_ENABLED=false
WEBDAV_URL=          # 坚果云等 WebDAV 服务
WEBDAV_USERNAME=
WEBDAV_PASSWORD=
```

### LLM 配置建议

| 场景 | 推荐配置 | 费用 |
|------|----------|------|
| 个人用户 | DeepSeek API | ≈ ¥0.01/份合同 |
| 企业内网 | Ollama 本地模型 | 免费（需 GPU） |
| 高精度需求 | OpenAI GPT-4 | ≈ ¥0.1/份合同 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        手机端 PWA                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ 拍照/上传   │  │ WebSocket   │  │ 本地缓存            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      电脑端 (FastAPI)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ OCR 引擎    │  │ Agent 编排  │  │ LLM 网关           │  │
│  │ PaddleOCR   │──│ 风险分析    │──│ DeepSeek/OpenAI    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ 知识库      │  │ SQLite      │  │ 同步引擎           │  │
│  │ 规则 + 法规 │  │ 数据库      │  │ WebDAV/Git/S3      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Python 3.10+ / FastAPI | 高性能异步框架 |
| 数据库 | SQLite + SQLAlchemy | 零配置，数据本地存储 |
| OCR | PaddleOCR-VL | 中文合同识别准确率高 |
| LLM | OpenAI 兼容 API | 支持多家大模型服务商 |
| 本地 LLM | Ollama | 可选，完全离线运行 |
| Embedding | sentence-transformers | 本地向量化，隐私安全 |
| 前端 | 纯 HTML/CSS/JS | 无框架依赖，PWA 离线可用 |
| 同步 | WebDAV / Git / S3 | 多设备数据同步 |

## 项目结构

```
clause-light/
├── server/              # 电脑端后端
│   ├── main.py          # FastAPI 入口
│   ├── config.py        # 配置管理
│   ├── api/             # API 路由
│   ├── core/            # 核心逻辑（OCR、LLM、Agent）
│   ├── models/          # 数据模型
│   └── static/          # Web 管理面板前端
│
├── mobile/              # 手机端 PWA（待实现）
│
├── asset/               # Logo、图标等资源
│
├── shared/              # 共享数据
│   ├── rules/           # 知识库规则（JSON）
│   └── laws/            # 法规条文（JSON）
│
├── data/                # 运行时数据（gitignored）
│
├── docker/              # Docker 配置
│
└── docs/                # 文档
```

## 常见问题

### Q: 启动报错 "ModuleNotFoundError: No module named 'xxx'"

```bash
pip install -r requirements.txt
```

### Q: PaddleOCR 安装失败

PaddleOCR 需要额外的系统依赖：

```bash
# Ubuntu/Debian
sudo apt-get install libglib2.0-0 libgl1-mesa-glx

# macOS
brew install libgl1-mesa-glx
```

### Q: 如何使用本地 Ollama 模型？

1. 安装 Ollama：https://ollama.com
2. 拉取模型：`ollama pull qwen2.5:7b`
3. 在 `.env` 中配置：`OLLAMA_ENDPOINT=http://localhost:11434`
4. 在管理面板「设置」页面启用本地模型

### Q: 如何备份数据？

数据存储在 `data/` 目录：
- `clause_light.db` — 数据库
- `uploads/` — 上传的合同文件

推荐定期备份整个 `data/` 目录，或使用同步功能。

### Q: 如何配置 HTTPS？

推荐使用 Nginx 反向代理：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 贡献

欢迎贡献代码、知识库规则或提出建议！详见 [CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## License

MIT
