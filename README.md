# ClauseLight（合同红绿灯）

> 拍照上传合同，红黄绿三色标注风险，告诉你哪些条款对你不利、建议怎么改。

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

### 安装

```bash
git clone https://github.com/your-username/clause-light.git
cd clause-light
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key
```

### 启动

```bash
# 初始化数据库和规则库
python scripts/init_db.py
python scripts/import_rules.py

# 启动服务
python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

### 访问

- **管理面板**：http://localhost:8080/admin/
- **手机端**：手机浏览器访问 http://你的电脑IP:8080/mobile/

## 配置说明

在 `.env` 文件中配置：

```bash
# LLM API Key（至少配一个）
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_OPENAI_API_KEY=sk-xxx

# 本地 Ollama（可选）
OLLAMA_ENDPOINT=http://localhost:11434

# 服务配置
HOST=0.0.0.0
PORT=8080
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python + FastAPI + SQLite |
| OCR | PaddleOCR-VL |
| LLM | OpenAI 兼容 API / Ollama |
| Embedding | sentence-transformers |
| 前端 | 纯 HTML/CSS/JS |
| 手机端 | PWA |
| 同步 | WebDAV / Git / S3 |

## 项目结构

```
clause-light/
├── server/          # 电脑端后端
├── mobile/          # 手机端 PWA
├── shared/          # 知识库规则 + 法规
├── data/            # 运行时数据（gitignored）
├── scripts/         # 工具脚本
├── docker/          # Docker 配置
└── docs/            # 文档
```

## 贡献

欢迎贡献知识库规则！详见 [CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## License

MIT
