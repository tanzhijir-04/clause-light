<p align="center">
  <img src="asset/合同红绿灯-app-icon--ios-android-.svg" width="120" alt="合同红绿灯 App Icon" />
</p>

<h1 align="center">合同红绿灯</h1>

<h3 align="center">ClauseLight — 开源合同风险审查工具</h3>

<p align="center">
  拍照上传合同，红黄绿三色标注风险，告诉你哪些条款对你不利、建议怎么改。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License" />
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="Python" />
  <img src="https://img.shields.io/badge/LLM-OpenAI%20Compatible-brightgreen" alt="LLM" />
  <img src="https://img.shields.io/badge/OCR-PaddleOCR-blue" alt="OCR" />
</p>

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 项目定位](#11-项目定位)
  - [1.2 核心能力](#12-核心能力)
  - [1.3 适用场景](#13-适用场景)
- [2. 快速开始](#2-快速开始)
  - [2.1 环境要求](#21-环境要求)
  - [2.2 本地安装](#22-本地安装)
  - [2.3 Docker 部署](#23-docker-部署)
  - [2.4 首次使用](#24-首次使用)
- [3. 系统架构](#3-系统架构)
  - [3.1 总体架构](#31-总体架构)
  - [3.2 技术栈](#32-技术栈)
  - [3.3 目录结构](#33-目录结构)
- [4. 核心功能](#4-核心功能)
  - [4.1 合同上传与 OCR 识别](#41-合同上传与-ocr-识别)
  - [4.2 三段式 Agent 分析流水线](#42-三段式-agent-分析流水线)
  - [4.3 原文标注视图](#43-原文标注视图)
  - [4.4 知识库与法规引擎](#44-知识库与法规引擎)
  - [4.5 多设备同步](#45-多设备同步)
- [5. 配置参考](#5-配置参考)
  - [5.1 环境变量](#51-环境变量)
  - [5.2 LLM 提供商配置](#52-llm-提供商配置)
  - [5.3 OCR 配置](#53-ocr-配置)
  - [5.4 同步配置](#54-同步配置)
- [6. API 参考](#6-api-参考)
  - [6.1 合同接口](#61-合同接口)
  - [6.2 知识库接口](#62-知识库接口)
  - [6.3 同步接口](#63-同步接口)
  - [6.4 设置接口](#64-设置接口)
- [7. 前端架构](#7-前端架构)
  - [7.1 设计系统](#71-设计系统)
  - [7.2 页面与路由](#72-页面与路由)
  - [7.3 组件库](#73-组件库)
- [8. 部署指南](#8-部署指南)
  - [8.1 生产环境部署](#81-生产环境部署)
  - [8.2 Nginx 反向代理](#82-nginx-反向代理)
  - [8.3 HTTPS 配置](#83-https-配置)
- [9. 常见问题](#9-常见问题)
- [10. 贡献指南](#10-贡献指南)
- [11. 许可证](#11-许可证)

---

## 1. 概述

### 1.1 项目定位

**合同红绿灯（ClauseLight）** 是一个开源的合同风险审查工具。它的核心理念是：

> 让每个人都能在签署合同前，像有律师陪着一样，清楚知道每条条款的风险。

传统合同审查依赖专业律师，成本高、周期长。合同红绿灯通过 **OCR + LLM + 知识库** 三引擎协作，实现：

- **秒级响应** — 上传后 30~60 秒出结果
- **零门槛** — 不需要法律背景，通俗解释让外行也能看懂
- **可进化** — 用户反馈自动优化规则，越用越准

### 1.2 核心能力

| 能力 | 描述 | 状态 |
|------|------|------|
| 📸 拍照即审 | 手机拍照或上传 PDF，自动 OCR 识别文字 | ✅ 已实现 |
| 🚦 三色标注 | 红/黄/绿三色标注每条条款的风险等级 | ✅ 已实现 |
| 📝 原文标注视图 | 完整合同原文 + 荧光笔高亮 + 右侧批注面板 | ✅ 已实现 |
| 💬 通俗解释 | 用大白话告诉你每条条款意味着什么 | ✅ 已实现 |
| ✏️ 修改建议 | 给出具体的修改措辞，可一键复制 | ✅ 已实现 |
| 📊 严重度评分 | 1-10 分量化每条风险的严重程度 | ✅ 已实现 |
| 🧠 自进化知识库 | 用户反馈自动优化规则，越用越准 | ✅ 已实现 |
| 📱 双端架构 | 电脑端全功能管理 + 手机端 PWA 分析 | ✅ 已实现 |
| 🔒 本地优先 | 数据默认不离开你的设备 | ✅ 已实现 |
| 🤖 多 LLM 支持 | DeepSeek / OpenAI / Ollama 本地模型 | ✅ 已实现 |
| ☁️ 多设备同步 | WebDAV / Git / S3 同步 | ✅ 已实现 |

### 1.3 适用场景

- **个人用户** — 签租房合同、劳动合同前自查风险
- **小微企业** — 没有法务部门，用 AI 辅助合同审查
- **自由职业者** — 审查外包合同、服务协议
- **学习研究** — 了解合同法风险条款的识别方法

---

## 2. 快速开始

### 2.1 环境要求

| 依赖 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.10 | 3.11+ | 核心运行时 |
| pip | 22.0 | 最新 | 包管理器 |
| Git | 2.30 | 最新 | 版本控制 |
| Ollama | — | 最新 | 可选，本地 LLM |

> **提示**：如果你只需要使用远程 API（如 DeepSeek），不需要安装 Ollama。

### 2.2 本地安装

#### 步骤 1：克隆项目

```bash
git clone https://github.com/tanzhijir-04/clause-light.git
cd clause-light
```

#### 步骤 2：创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

#### 步骤 3：安装依赖

```bash
pip install -r requirements.txt
```

> **注意**：PaddleOCR 首次运行会自动下载模型文件（约 100MB），请确保网络通畅。

#### 步骤 4：配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env，填入你的 LLM API Key（至少配一个）
```

#### 步骤 5：启动服务

```bash
# 方式 A：一条命令启动（推荐）
python server/main.py

# 方式 B：使用 uvicorn 启动（支持热重载）
python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

#### 步骤 6：访问应用

| 入口 | 地址 | 说明 |
|------|------|------|
| 管理面板 | http://localhost:8080/admin/ | 电脑端全功能管理界面 |
| 手机端 | http://你的电脑IP:8080/mobile/ | 手机浏览器访问，可添加到主屏幕 |
| API 文档 | http://localhost:8080/docs | FastAPI 自动生成的 Swagger 文档 |

### 2.3 Docker 部署

#### 步骤 1：配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

#### 步骤 2：启动容器

```bash
cd docker

# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 步骤 3：访问

与本地安装相同，管理面板默认运行在 http://localhost:8080/admin/。

> **提示**：Docker 部署会自动处理 PaddleOCR 的系统依赖，无需手动安装。

### 2.4 首次使用

1. 打开管理面板，点击「上传合同」或直接拖放文件
2. 支持 PDF 和图片格式（PNG / JPG / BMP / TIFF）
3. 等待 30~60 秒，系统自动完成 OCR → 解析 → 风险分析
4. 分析完成后自动跳转到详情页
5. 切换到「原文标注」视图，查看高亮标注的风险条款
6. 点击高亮段落，右侧弹出批注面板，查看详细分析

---

## 3. 系统架构

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        手机端 PWA                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ 拍照 / 上传  │  │ WebSocket    │  │ IndexedDB 本地缓存     │ │
│  │ HTML5 Camera │  │ Socket.IO    │  │ 离线可用               │ │
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
│  │ 规则 + 法规 │◀──▶│  数据库     │    │ WebDAV / Git / S3   │ │
│  └─────────────┘    └─────────────┘    └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 技术栈

<table>
  <thead>
    <tr><th>层级</th><th>技术</th><th>用途</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>后端框架</strong></td><td>Python 3.10+ / FastAPI</td><td>高性能异步 Web 框架，支持 WebSocket</td></tr>
    <tr><td><strong>数据库</strong></td><td>SQLite + SQLAlchemy ORM</td><td>零配置，数据本地存储，异步操作</td></tr>
    <tr><td><strong>OCR</strong></td><td>PaddleOCR-VL</td><td>中文合同文字识别，准确率高</td></tr>
    <tr><td><strong>LLM 调用</strong></td><td>OpenAI SDK（兼容格式）</td><td>统一网关，支持多家大模型服务商</td></tr>
    <tr><td><strong>本地 LLM</strong></td><td>Ollama</td><td>可选，完全离线运行，隐私安全</td></tr>
    <tr><td><strong>Embedding</strong></td><td>sentence-transformers</td><td>本地向量化，知识库语义检索</td></tr>
    <tr><td><strong>前端</strong></td><td>纯 HTML / CSS / JavaScript</td><td>无框架依赖，PWA 离线可用</td></tr>
    <tr><td><strong>同步</strong></td><td>WebDAV / Git / S3</td><td>多设备数据同步</td></tr>
  </tbody>
</table>

### 3.3 目录结构

```
clause-light/
│
├── server/                    # 电脑端后端
│   ├── main.py                # FastAPI 入口，单文件启动
│   ├── config.py              # 配置管理（环境变量 + 配置文件）
│   │
│   ├── api/                   # API 路由层
│   │   ├── contracts.py       #   合同分析接口
│   │   ├── knowledge.py       #   知识库接口
│   │   ├── sync.py            #   同步接口
│   │   └── ws.py              #   WebSocket 接口
│   │
│   ├── core/                  # 核心业务逻辑
│   │   ├── agent.py           #   Agent Harness（三段式流程编排）
│   │   ├── ocr.py             #   PaddleOCR 封装
│   │   ├── llm.py             #   LLM 网关（多模型路由 + 故障转移）
│   │   ├── embedding.py       #   Embedding 服务
│   │   ├── knowledge.py       #   知识库引擎
│   │   └── prompts/           #   Prompt 模板
│   │       ├── classify.py    #     合同分类
│   │       ├── split.py       #     条款拆分
│   │       ├── analyze.py     #     风险分析
│   │       ├── suggest.py     #     修改建议
│   │       └── score.py       #     评分聚合
│   │
│   ├── models/                # 数据模型
│   │   └── database.py        #   SQLAlchemy 模型 + SQLite 引擎
│   │
│   ├── sync/                  # 同步引擎
│   │   ├── webdav.py          #   WebDAV 同步（坚果云等）
│   │   ├── git_sync.py        #   Git 同步
│   │   └── s3_sync.py         #   S3 同步
│   │
│   └── static/                # Web 管理面板前端
│       ├── index.html         #   主入口
│       ├── css/               #   样式
│       │   ├── tokens.css     #     设计令牌（CSS 自定义属性）
│       │   ├── base.css       #     重置 + 基础样式
│       │   ├── layout.css     #     布局（侧边栏 + 主内容区）
│       │   ├── components.css #     组件样式
│       │   └── pages.css      #     页面特定样式
│       └── js/                #   JavaScript
│           ├── app.js         #     主应用（路由 + 主题 + 初始化）
│           ├── router.js      #     Hash 路由器
│           ├── theme.js       #     主题切换
│           ├── api.js         #     API 调用封装
│           ├── icons.js       #     SVG 图标
│           ├── components.js  #     共享 UI 组件
│           └── pages/         #     页面模块
│               ├── dashboard.js
│               ├── contracts.js
│               ├── contractDetail.js  # 合同详情（含原文标注视图）
│               ├── knowledge.js
│               ├── models.js
│               ├── settings.js
│               └── sync.js
│
├── mobile/                    # 手机端 PWA
│   ├── index.html             #   主入口
│   ├── css/style.css          #   移动端样式
│   ├── js/
│   │   ├── app.js             #   主应用逻辑
│   │   ├── ocr.js             #   OCR 通信
│   │   └── agent.js           #   Agent Harness（手机端精简版）
│   ├── manifest.json          #   PWA 清单
│   └── sw.js                  #   Service Worker（离线缓存）
│
├── shared/                    # 共享数据
│   ├── rules/                 #   知识库规则（JSON）
│   │   ├── general.json       #     通用规则
│   │   ├── rental.json        #     租赁合同规则
│   │   ├── labor.json         #     劳动合同规则
│   │   ├── renovation.json    #     装修合同规则
│   │   └── outsourcing.json   #     外包合同规则
│   └── laws/                  #   法规条文（JSON）
│       ├── civil_code.json    #     民法典
│       └── labor_law.json     #     劳动法
│
├── asset/                     # Logo、图标等资源
│
├── data/                      # 运行时数据（gitignored）
│   ├── clause_light.db        #   SQLite 数据库
│   └── uploads/               #   上传的合同文件
│
├── docker/                    # Docker 配置
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── docs/                      # 文档
│   ├── TECHNICAL.md           #   技术文档
│   ├── CONTRIBUTING.md        #   贡献指南
│   └── API.md                 #   API 文档
│
├── CLAUDE.md                  # Claude Code 项目配置
├── AGENT.md                   # Agent 行为规范
├── PRD-ClauseLight.md         # 产品需求文档
├── requirements.txt           # Python 依赖
├── pyproject.toml             # 项目元数据
└── README.md                  # 本文件
```

---

## 4. 核心功能

### 4.1 合同上传与 OCR 识别

**工作流程**：

```
用户上传文件 → 格式校验 → 保存到 uploads/ → PaddleOCR 识别 → 返回全文
```

**支持格式**：

| 格式 | 扩展名 | 最大大小 | 说明 |
|------|--------|---------|------|
| PDF | `.pdf` | 20 MB | 自动提取每一页 |
| PNG | `.png` | 20 MB | 推荐，识别率最高 |
| JPEG | `.jpg` / `.jpeg` | 20 MB | 压缩损失可能影响识别 |
| BMP | `.bmp` | 20 MB | 无损，文件较大 |
| TIFF | `.tiff` | 20 MB | 多页 TIFF 支持 |

**OCR 配置**：

```python
# server/config.py 中的默认配置
OCR_USE_GPU = False        # 是否使用 GPU 加速
OCR_LANG = 'ch'            # 语言（ch=中文，en=英文）
OCR_CONFIDENCE = 0.7       # 最低置信度阈值
```

> **提示**：如果 OCR 置信度低于 0.7，系统会在日志中发出警告，但仍会继续分析。

### 4.2 三段式 Agent 分析流水线

合同分析采用 **三段式 Prompt Chaining + Parallelization** 架构：

```
        ┌──────────────────────────────────────────────────────┐
        │                  OCR 识别全文                        │
        └───────────────────────┬──────────────────────────────┘
                                │
                                ▼
        ┌──────────────────────────────────────────────────────┐
        │         Stage 1: 结构解析（LLM）                    │
        │   全文 → 拆分为条款 → 识别合同类型                   │
        │   输出: ClauseItem[] (编号、标题、内容、类型)         │
        └───────────────────────┬──────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │   知识库检索           │
                    │   前 500 字 + 类型     │
                    │   → 匹配相关规则       │
                    └───────────┬───────────┘
                                │
                                ▼
        ┌──────────────────────────────────────────────────────┐
        │         Stage 2: 并行风险评估（5 个 Worker）          │
        │                                                      │
        │   ┌──────────┐ ┌──────────┐ ┌──────────┐            │
        │   │ 公平性   │ │ 财务风险 │ │ 知识产权 │            │
        │   │ Worker   │ │ Worker   │ │ Worker   │            │
        │   └──────────┘ └──────────┘ └──────────┘            │
        │   ┌──────────┐ ┌──────────┐                         │
        │   │ 争议解决 │ │ 通用风险 │                         │
        │   │ Worker   │ │ Worker   │                         │
        │   └──────────┘ └──────────┘                         │
        │                                                      │
        │   每个 Worker 独立分析所有条款，输出 ClauseRisk[]     │
        └───────────────────────┬──────────────────────────────┘
                                │
                                ▼
        ┌──────────────────────────────────────────────────────┐
        │         Stage 3: 聚合评分（LLM）                     │
        │   合并所有维度的风险 → 综合评分 → 生成建议            │
        │   输出: 0-100 分 + 签署建议 + 一句话总结             │
        └───────────────────────┬──────────────────────────────┘
                                │
                                ▼
        ┌──────────────────────────────────────────────────────┐
        │         结果组装                                     │
        │   合并解析结果 + 风险评估 → 最终 AnalysisResult      │
        └──────────────────────────────────────────────────────┘
```

**AnalysisResult 数据结构**：

```python
@dataclass
class AnalysisResult:
    contract_id: str           # 合同 ID
    contract_type: str         # 合同类型（中文）
    contract_type_en: str      # 合同类型（英文 key）
    overall_score: int         # 综合评分 0-100
    recommendation: str        # 签署建议: sign / negotiate_first / reject
    summary: str               # 一句话总结
    model_used: str            # 使用的 LLM 模型
    clauses: list[dict]        # 条款分析列表
    red_count: int             # 高风险条款数
    yellow_count: int          # 中风险条款数
    green_count: int           # 低风险条款数
    needs_review: list[str]    # 需人工复核的条款 ID
    top_risks: list[str]       # 主要风险摘要
    ocr_text: str              # OCR 识别的合同全文
    error: str                 # 错误信息（空=成功）
```

**单条条款的数据结构**：

```python
{
    "clause_number": "第三条",           # 条款编号
    "title": "租金及支付方式",            # 条款标题
    "content": "月租金为人民币 8,500...", # 条款原文
    "type": "financial",                 # 风险维度
    "risk_level": "red",                 # red / yellow / green
    "risk_type": "高额滞纳金",           # 风险类型
    "risk_summary": "逾期滞纳金每日5%...", # 问题描述
    "plain_explanation": "如果你晚交...", # 通俗解释
    "severity_score": 8,                 # 严重度 1-10
    "suggested_clause": "滞纳金改为...",  # 修改建议
    "legal_basis": "民法典第585条...",    # 法律依据
    "unfavorable_to": "乙方",            # 不利方
    "needs_review": false                # 是否需人工复核
}
```

### 4.3 原文标注视图

原文标注视图是合同详情页的核心功能，提供两种查看模式：

#### 条款列表视图

以卡片形式展示所有条款，每张卡片包含：
- 条款编号 + 风险徽章
- 风险摘要
- 修改建议预览（蓝色背景）
- 法律依据预览（灰色斜体）

#### 原文标注视图

完整合同原文 + 荧光笔高亮标注：

| 风险等级 | 高亮样式 | 说明 |
|---------|---------|------|
| 🔴 高风险（red） | 红色左边框 3px + 红色背景 12% 透明度 | 需要重点关注 |
| 🟡 中风险（yellow） | 黄色左边框 3px + 黄色背景 10% 透明度 | 建议修改 |
| 🟢 低风险（green） | 无高亮 | 正常条款 |

**交互功能**：

- **点击高亮段落** — 右侧弹出批注面板，显示风险详情
- **悬停高亮段落** — 加深背景，显示条款编号标签
- **风险导航** — 「上一条」/「下一条」按钮在 red + yellow 条款间跳转
- **风险分布条** — 点击色段筛选对应风险等级的高亮
- **自动滚动** — 首次进入自动滚动到第一个红色条款

**批注面板内容**：

1. 问题摘要（riskSummary）
2. 通俗解释（plainExplanation）
3. 法律依据（legalBasis）— 灰色斜体
4. 修改建议（suggestedClause）— 蓝色背景 + 左边框
5. 严重度条（10 个色块，根据 severityScore 填充）
6. 反馈按钮（标注准确 / 标注不准确）

**条款定位算法**：

```
输入: fullText（完整合同文本），clauses（条款数组）

对每条 clause:
  1. 优先用 clauseNumber + "\n" + clauseTitle 搜索锚点
  2. 找不到则用 clauseNumber 单独搜索
  3. 仍找不到则用 clauseContent 前 30 字符子串匹配
  4. 匹配失败则跳过该条款（不高亮，不崩溃）

按起始位置排序 → 处理重叠（取最高风险等级）→ 生成 HTML
```

### 4.4 知识库与法规引擎

**知识库结构**：

```
shared/
├── rules/                     # 风险识别规则
│   ├── general.json           #   通用规则（适用所有合同类型）
│   ├── rental.json            #   租赁合同专用规则
│   ├── labor.json             #   劳动合同专用规则
│   ├── renovation.json        #   装修合同专用规则
│   └── outsourcing.json       #   外包合同专用规则
└── laws/                      # 法规条文
    ├── civil_code.json        #   民法典相关条文
    └── labor_law.json         #   劳动法相关条文
```

**规则格式**：

```json
{
  "id": "general-001",
  "category": "通用",
  "text": "滞纳金或违约金超过合同金额20%的条款应标记为高风险",
  "confidence": 0.95,
  "keywords": ["滞纳金", "违约金", "罚款"],
  "legal_basis": "民法典第585条"
}
```

**自进化机制**：

1. 用户在批注面板点击「标注准确」或「标注不准确」
2. 反馈写入 `clause_analyses.user_feedback` 字段
3. 知识库引擎定期分析反馈，自动调整规则权重
4. 高置信度规则优先使用，低置信度规则降权

### 4.5 多设备同步

支持三种同步后端：

| 后端 | 协议 | 推荐场景 | 说明 |
|------|------|---------|------|
| WebDAV | HTTPS | 个人用户 | 坚果云、NextCloud 等 |
| Git | SSH/HTTPS | 开发者 | 同步到私有仓库 |
| S3 | HTTPS | 企业用户 | AWS S3、MinIO 等 |

---

## 5. 配置参考

### 5.1 环境变量

在 `.env` 文件中配置（参考 `.env.example`）：

```bash
# ╔══════════════════════════════════════════════════════════╗
# ║  LLM 配置（至少配一个）                                  ║
# ╚══════════════════════════════════════════════════════════╝

# DeepSeek（推荐，性价比最高）
LLM_DEEPSEEK_API_KEY=sk-xxx

# OpenAI
LLM_OPENAI_API_KEY=sk-xxx

# 通义千问
LLM_QWEN_API_KEY=sk-xxx

# ╔══════════════════════════════════════════════════════════╗
# ║  本地 LLM（可选，需要先安装 Ollama）                       ║
# ╚══════════════════════════════════════════════════════════╝

OLLAMA_ENDPOINT=http://localhost:11434

# ╔══════════════════════════════════════════════════════════╗
# ║  服务配置                                                ║
# ╚══════════════════════════════════════════════════════════╝

HOST=0.0.0.0
PORT=8080
DEBUG=false

# ╔══════════════════════════════════════════════════════════╗
# ║  OCR 配置                                                ║
# ╚══════════════════════════════════════════════════════════╝

OCR_USE_GPU=false

# ╔══════════════════════════════════════════════════════════╗
# ║  同步配置（可选）                                         ║
# ╚══════════════════════════════════════════════════════════╝

SYNC_ENABLED=false
WEBDAV_URL=          # 坚果云等 WebDAV 服务地址
WEBDAV_USERNAME=     # WebDAV 用户名
WEBDAV_PASSWORD=     # WebDAV 密码
```

### 5.2 LLM 提供商配置

**配置优先级**：配置文件 `data/llm_config.json` > 环境变量 > 硬编码默认值

**推荐配置方案**：

| 场景 | 推荐方案 | 费用 | 说明 |
|------|---------|------|------|
| 个人日常使用 | DeepSeek API | ≈ ¥0.01/份合同 | 性价比最高 |
| 企业内网部署 | Ollama + qwen2.5:32b | 免费（需 GPU） | 数据不出内网 |
| 高精度需求 | OpenAI GPT-4 | ≈ ¥0.1/份合同 | 分析质量最好 |
| 混合方案 | DeepSeek 主力 + Ollama 兜底 | 按需 | 推荐生产环境 |

**Ollama 本地模型推荐**：

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取推荐模型
ollama pull qwen2.5:7b     # 轻量级，4GB 显存即可
ollama pull qwen2.5:32b    # 高精度，需要 24GB 显存
```

### 5.3 OCR 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `OCR_USE_GPU` | `False` | 是否使用 GPU 加速（需 CUDA） |
| `OCR_LANG` | `ch` | 识别语言（`ch`=中文，`en`=英文） |
| `OCR_CONFIDENCE` | `0.7` | 最低置信度阈值 |

### 5.4 同步配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SYNC_ENABLED` | `False` | 是否启用同步 |
| `WEBDAV_URL` | — | WebDAV 服务器地址 |
| `WEBDAV_USERNAME` | — | WebDAV 用户名 |
| `WEBDAV_PASSWORD` | — | WebDAV 密码 |

---

## 6. API 参考

所有 API 返回 JSON 格式。Swagger 文档地址：http://localhost:8080/docs

### 6.1 合同接口

#### `GET /api/contracts/`

获取合同列表，支持筛选。

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `search` | string | 搜索关键词（匹配标题和类型） |
| `type` | string | 合同类型筛选（rental / labor / ...） |
| `risk` | string | 风险等级筛选（red / yellow / green） |

**响应示例**：

```json
[
  {
    "id": "a1b2c3d4",
    "title": "房屋租赁合同",
    "type": "租赁合同",
    "typeEn": "rental",
    "score": 42,
    "riskLevel": "red",
    "redCount": 5,
    "yellowCount": 3,
    "greenCount": 2,
    "createdAt": "2026-06-12",
    "status": "analyzed",
    "model": "deepseek-chat"
  }
]
```

#### `GET /api/contracts/{contract_id}`

获取合同详情 + 分析结果。

**响应包含**：

| 字段 | 说明 |
|------|------|
| `fullText` | OCR 识别的合同全文（用于原文标注视图） |
| `clauses[]` | 条款分析数组，每条包含风险详情 |
| `score` | 综合评分 0-100 |
| `riskLevel` | 整体风险等级 |
| `recommendation` | 签署建议（sign / negotiate_first / reject） |

#### `POST /api/contracts/analyze`

上传并分析合同。

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | ✅ | 合同文件（PDF / 图片） |
| `contract_type` | string | ❌ | 合同类型提示 |

**响应**：

```json
{
  "success": true,
  "contractId": "a1b2c3d4",
  "score": 42,
  "riskLevel": "red"
}
```

#### `POST /api/contracts/{contract_id}/feedback`

提交条款反馈。

**请求**：`application/x-www-form-urlencoded`

| 字段 | 类型 | 说明 |
|------|------|------|
| `clause_analysis_id` | string | 条款分析 ID |
| `feedback` | string | `correct` 或 `incorrect` |

### 6.2 知识库接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/knowledge/rules` | 获取规则列表 |
| `POST` | `/api/knowledge/rules` | 创建新规则 |
| `PUT` | `/api/knowledge/rules/{id}` | 更新规则 |
| `DELETE` | `/api/knowledge/rules/{id}` | 删除规则 |
| `GET` | `/api/knowledge/stats` | 知识库统计 |
| `GET` | `/api/knowledge/pending` | 待审核规则 |
| `GET` | `/api/knowledge/laws` | 法规条文列表 |

### 6.3 同步接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/sync/config` | 获取同步配置 |
| `PUT` | `/api/sync/config` | 更新同步配置 |
| `POST` | `/api/sync/push` | 推送到远程 |
| `POST` | `/api/sync/pull` | 从远程拉取 |
| `GET` | `/api/sync/log` | 同步日志 |

### 6.4 设置接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/settings/llm` | 获取 LLM 配置 |
| `PUT` | `/api/settings/llm` | 更新 LLM 配置 |
| `POST` | `/api/settings/llm/test` | 测试远程 API 连接 |
| `POST` | `/api/settings/llm/test-local` | 测试本地 Ollama 连接 |
| `GET` | `/api/models/status` | 模型状态 |

---

## 7. 前端架构

### 7.1 设计系统

前端采用 **Notion 风格设计令牌系统**，支持明暗双主题。

**设计令牌分类**：

| 类别 | 令牌示例 | 说明 |
|------|---------|------|
| 背景 | `--bg-app`, `--bg-surface`, `--bg-elevated` | 5 级背景层次 |
| 文字 | `--text-primary`, `--text-secondary`, `--text-tertiary` | 3 级文字层次 |
| 边框 | `--border-default`, `--border-strong`, `--border-subtle` | 3 级边框强度 |
| 强调色 | `--accent`, `--accent-hover`, `--accent-subtle` | 主题强调色 |
| 风险色 | `--risk-red`, `--risk-yellow`, `--risk-green` | 三色风险系统 |
| 阴影 | `--shadow-xs` ~ `--shadow-lg` | 4 级阴影 |
| 间距 | `--sp-1` (4px) ~ `--sp-12` (48px) | 9 级间距 |
| 圆角 | `--radius-sm` ~ `--radius-full` | 5 级圆角 |
| 字号 | `--text-xs` (11px) ~ `--text-2xl` (30px) | 8 级字号 |

**风险色系统**：

```
--risk-red:       #EF4444    高风险
--risk-red-bg:    #FEF2F2    高风险背景
--risk-red-text:  #991B1B    高风险文字
--risk-red-border:#FECACA    高风险边框

--risk-yellow:       #F59E0B    中风险
--risk-yellow-bg:    #FFFBEB    中风险背景
--risk-yellow-text:  #92400E    中风险文字
--risk-yellow-border:#FDE68A    中风险边框

--risk-green:       #10B981    低风险
--risk-green-bg:    #ECFDF5    低风险背景
--risk-green-text:  #065F46    低风险文字
--risk-green-border:#A7F3D0    低风险边框
```

### 7.2 页面与路由

**路由系统**：Hash 路由（`#/path`），支持参数解析。

| 路由 | 页面 | 说明 |
|------|------|------|
| `#/dashboard` | DashboardPage | 仪表盘 |
| `#/contracts` | ContractsPage | 合同列表 |
| `#/contracts/{id}` | ContractDetailPage | 合同详情（含原文标注） |
| `#/knowledge` | KnowledgePage | 知识库管理 |
| `#/sync` | SyncPage | 同步管理 |
| `#/settings` | SettingsPage | 系统设置 |
| `#/models` | ModelsPage | 模型管理 |

**页面渲染模式**：每个页面是一个 plain object，实现 `async render(params)` 方法，返回 HTML 字符串。无虚拟 DOM，纯字符串拼接。

### 7.3 组件库

| 组件 | 函数 | 说明 |
|------|------|------|
| 风险徽章 | `Components.RiskBadge(level)` | 彩色圆点 + 文字标签 |
| 统计卡片 | `Components.RiskDistBar(r, y, g)` | 水平分段风险分布条 |
| 可交互分布条 | `Components.RiskDistInteractive(r, y, g, filter, cb)` | 可点击筛选的分布条 |
| 评分圆环 | `Components.ScoreRing(score, size)` | SVG 圆形进度环 |
| 严重度条 | `Components.SeverityBar(score)` | 10 格可视化严重度 |
| 开关 | `Components.Toggle(id, on)` | 滑动开关 |
| 上传区域 | `Components.UploadZone()` | 拖放上传区 |
| 侧边栏 | `Components.Sidebar(activePage)` | 导航侧边栏 |
| Toast | `Components.toast(msg, type)` | 通知弹窗 |

---

## 8. 部署指南

### 8.1 生产环境部署

```bash
# 1. 克隆并安装
git clone https://github.com/tanzhijir-04/clause-light.git
cd clause-light
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
# 编辑 .env 填入配置

# 3. 启动（使用 nohup 或 systemd 保持后台运行）
nohup python server/main.py > app.log 2>&1 &
```

### 8.2 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 合同文件上传大小限制
    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 支持
    location /socket.io {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 8.3 HTTPS 配置

推荐使用 Let's Encrypt 免费证书：

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 自动申请并配置
sudo certbot --nginx -d your-domain.com
```

---

## 9. 常见问题

<details>
<summary><strong>Q: 启动报错 "ModuleNotFoundError: No module named 'xxx'"</strong></summary>

```bash
pip install -r requirements.txt
```

确保已激活虚拟环境且依赖安装完整。
</details>

<details>
<summary><strong>Q: PaddleOCR 安装失败</strong></summary>

PaddleOCR 需要额外的系统依赖：

```bash
# Ubuntu/Debian
sudo apt-get install libglib2.0-0 libgl1-mesa-glx

# macOS
brew install libgl1-mesa-glx
```

Windows 用户通常无需额外安装。
</details>

<details>
<summary><strong>Q: 如何使用本地 Ollama 模型？</strong></summary>

1. 安装 Ollama：https://ollama.com
2. 拉取模型：`ollama pull qwen2.5:7b`
3. 在 `.env` 中配置：`OLLAMA_ENDPOINT=http://localhost:11434`
4. 在管理面板「设置」页面启用本地模型
</details>

<details>
<summary><strong>Q: 如何备份数据？</strong></summary>

数据存储在 `data/` 目录：
- `clause_light.db` — 数据库
- `uploads/` — 上传的合同文件

推荐定期备份整个 `data/` 目录，或配置同步功能自动备份。
</details>

<details>
<summary><strong>Q: 上传后分析失败怎么办？</strong></summary>

1. 检查日志：`tail -f app.log`
2. 确认 LLM API Key 已配置且有效
3. 尝试切换其他 LLM 提供商
4. 检查网络连接（远程 API）或 Ollama 是否运行（本地模型）
</details>

<details>
<summary><strong>Q: 如何查看 API 文档？</strong></summary>

启动服务后访问 http://localhost:8080/docs，FastAPI 自动生成 Swagger 交互式文档。
</details>

---

## 10. 贡献指南

欢迎贡献代码、知识库规则或提出建议！详见 [CONTRIBUTING.md](docs/CONTRIBUTING.md)。

**快速贡献方式**：

- 🐛 报告 Bug → [GitHub Issues](https://github.com/tanzhijir-04/clause-light/issues)
- 💡 提出建议 → [GitHub Discussions](https://github.com/tanzhijir-04/clause-light/discussions)
- 📝 贡献规则 → 编辑 `shared/rules/*.json`
- 🔧 提交代码 → Fork → Branch → PR

---

## 11. 许可证

[MIT License](LICENSE) — 自由使用、修改、分发。
