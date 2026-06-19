# ClauseLight — 产品需求文档（PRD）

**项目名称**：合同红绿灯
**仓库名**：clause-light
**版本**：v1.0
**日期**：2026-06-12
**性质**：开源项目（MIT License）

---

## 一、产品定位

普通人看不懂的合同，拍照上传后，用红黄绿三色逐条标注风险等级，告诉你哪些条款对你不利、建议怎么改。内置可自进化的法律知识库，由专属 Agent 驱动分析引擎，数据全部本地存储，支持多协议云同步。

**一句话**：拍照 → 看风险 → 知道怎么改。

---

## 二、目标用户

| 角色 | 场景 | 核心诉求 |
|------|------|----------|
| 租房的年轻人 | 签租赁合同 | 看懂押金、违约金、退租条件 |
| 职场人 | 签劳动合同 | 看懂竞业协议、加班条款、赔偿标准 |
| 自由职业者 | 签外包/合作协议 | 怕被坑，需要专业级审查 |
| 装修/买车消费者 | 签大额消费合同 | 条款复杂，怕漏看 |
| 小团队负责人 | 签商务合同 | 请不起法务，需要低成本审查 |

---

## 三、双端产品定义

本产品分为 **电脑端（全功能）** 和 **手机端（精简版）** 两个形态。

### 3.1 电脑端 — 全功能管理中枢

```
电脑端（全功能）
├── 合同分析（完整版：OCR + Agent + LLM）
├── 知识库管理（增删改查规则、法规更新、自动进化）
├── 用户反馈管理（审核对错、触发知识库进化）
├── 同步配置（WebDAV / Git / S3）
├── 数据导出（Markdown / PDF / JSON / CSV）
├── LLM 配置（API Key / 模型选择 / Ollama 地址）
├── 客户端连接管理（查看哪些手机连着、连接历史）
└── Web 管理面板
```

**使用场景**：回家后深度分析、管理知识库、配置系统、查看历史报告。

### 3.2 手机端 — 精简版（只做合同分析）

```
手机端（精简版，只做一件事）
├── 拍照 / 选择文件（图片 / PDF）
├── OCR 识别（本地 PaddleOCR-VL 或交给电脑/API）
├── 分析请求（发送给云端 API 或电脑端）
├── 结果展示（红黄绿 + 通俗解释 + 修改建议）
├── 用户反馈（标记对错，发送回电脑端用于知识库进化）
└── 历史记录查看（本地缓存）
```

**使用场景**：在外面签合同时，拍照快速扫一眼风险。

### 3.3 两端的关系

```
电脑端是中枢，手机端是延伸：
- 手机拍完合同 → 分析可以走云端 API（独立）或走电脑端（省钱）
- 手机上的用户反馈 → 同步回电脑端的知识库
- 电脑端配置的知识库 → 手机端可检索使用
- 电脑端是管理入口，手机端是使用入口
```

---

## 四、系统架构

### 4.1 总体架构

```
┌─────────────────────────────────────────────────────┐
│                    手机端（PWA）                      │
│                                                     │
│  拍照 → OCR → 条款拆解 → Agent Harness → Prompt 拼装│
│       → 调用 LLM API ──────────────────→ 云端       │
│       ← 接收分析结果 ←────────────────── 云端       │
│       → 知识库检索（Embedding 本地）                  │
│       → 结果展示 + 本地缓存                           │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket / HTTP
                       │（局域网直连，可选）
┌──────────────────────▼──────────────────────────────┐
│                  电脑端（本地服务）                    │
│                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 合同分析  │  │ 知识库引擎    │  │ LLM 网关     │  │
│  │ Agent    │  │ 自进化+检索   │  │ OpenAI/本地  │  │
│  │ Harness  │  │ Embedding    │  │ 多模型路由   │  │
│  └──────────┘  └──────────────┘  └──────────────┘  │
│                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ SQLite   │  │ 同步引擎      │  │ Web 管理面板 │  │
│  │ 数据库   │  │ WebDAV/Git/S3│  │ 知识库/设置  │  │
│  └──────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 4.2 两种运行模式

| 模式 | 手机 OCR | 知识库检索 | LLM 分析 | 需要什么 |
|------|---------|-----------|---------|---------|
| **独立模式** | 手机本地 | 手机本地 Embedding | 云端 API（OpenAI/DeepSeek/...） | 手机 + 网络 |
| **联动模式** | 手机本地 | 电脑端检索 | 电脑端调用 LLM | 手机 + 电脑同一网络 |
| **纯离线模式** | 手机本地 | 规则引擎兜底 | 无（仅粗筛） | 手机，无网络 |

### 4.3 连接方式

```
手机发现电脑：
1. 自动发现：mDNS/Bonjour 扫描局域网
2. 手动输入：电脑 IP:端口
3. 二维码：电脑端生成，手机扫码连接

连接建立后：
- WebSocket 双向通信
- 手机发送合同文本 + 请求
- 电脑端流式返回分析结果
- 支持断线重连，不丢失进度
```

---

## 五、技术栈（简单导向）

### 5.1 总体原则

- **能用现成库就不自己写**
- **能用 Python 就不用其他语言**
- **能用 SQLite 就不上 PostgreSQL**
- **能用 PWA 就不做原生 App**
- **能用规则引擎兜底就不强依赖 AI**

### 5.2 电脑端技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| 后端框架 | **Python + FastAPI** | 轻量、异步、部署简单、生态好 |
| 数据库 | **SQLite** | 零配置、单文件、嵌入式 |
| OCR | **PaddleOCR-VL** | 中文识别好、本地运行、开源 |
| Embedding | **sentence-transformers** | 本地运行、模型小（<100MB） |
| LLM 调用 | **OpenAI SDK（兼容格式）** | 统一接口，兼容 OpenAI/DeepSeek/通义千问等 |
| 本地 LLM | **Ollama** | 一键安装、模型管理方便 |
| 知识库存储 | **SQLite + JSON 文件** | 规则用 SQLite 管理，法规用 JSON 文件 |
| 同步 | **WebDAV（webdavclient3）/ Git（subprocess）/ S3（boto3）** | 三个库搞定 |
| Web 管理面板 | **纯 HTML + CSS + JS** | 无框架依赖、简单、轻量 |
| 启动方式 | **python server.py** 或 **Docker** | 最简部署 |

### 5.3 手机端技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| 应用形态 | **PWA** | 零安装、跨平台、手机浏览器直接用 |
| OCR | **PaddleOCR-VL（通过电脑端 API 或云端）** | 手机端不做本地 OCR（省算力），拍照后发送给电脑端或云端识别 |
| Embedding | **Transformers.js + ONNX** | 浏览器内运行，本地知识库检索 |
| 界面 | **纯 HTML + CSS + JS** | 无框架、轻量、加载快 |
| 本地存储 | **IndexedDB** | 浏览器端缓存历史记录 |
| 通信 | **WebSocket（Socket.IO 客户端）** | 与电脑端实时通信 |
| LLM 调用 | **通过电脑端代理 或 直接调云端 API** | 手机端不直接暴露 API Key |

### 5.4 LLM 网关配置

```yaml
# 配置示例
llm:
  # 远程 API（OpenAI 标准）
  providers:
    - name: "deepseek"
      base_url: "https://api.deepseek.com/v1"
      api_key: "sk-xxx"
      models:
        classification: "deepseek-chat"      # 分类用小模型
        analysis: "deepseek-chat"            # 分析用大模型
        explanation: "deepseek-chat"         # 解释用小模型

    - name: "openai"
      base_url: "https://api.openai.com/v1"
      api_key: "sk-xxx"
      models:
        analysis: "gpt-4o"

  # 本地模型（Ollama）
  local:
    endpoint: "http://localhost:11434"
    models:
      classification: "qwen2.5:7b"
      analysis: "qwen2.5:32b"
      explanation: "qwen2.5:7b"

  # 路由策略
  routing:
    default: "deepseek"           # 默认用哪个
    fallback: "openai"            # 备用
    local_priority: false         # 优先用本地模型
```

---

## 六、核心模块详细设计

### 模块 1：OCR 引擎（PaddleOCR-VL）

**电脑端完整版**：
- 直接调用 PaddleOCR-VL Python API
- 支持图片和 PDF
- 输出结构化文本（段落、条款层级）

**手机端**：
- 拍照后将图片发送给电脑端（联动模式）或跳过 OCR 步骤（由 Agent 处理）
- 不在手机本地运行 OCR（简化手机端实现）

**OCR 输出格式**：
```json
{
  "full_text": "合同全文纯文本",
  "structure": [
    {"clause_number": "第三条", "title": "付款方式", "content": "..."}
  ],
  "confidence_avg": 0.95
}
```

### 模块 2：合同分析 Agent

#### 2.1 Agent Harness（运行框架）

```
Agent Harness 控制的分析流程：

Step 1: 合同分类
  输入：合同全文
  输出：合同类型（租赁/劳动/装修/外包/借款/服务/其他）
  工具：LLM 分类 + 关键词规则兜底

Step 2: 条款拆解
  输入：合同全文 + 合同类型
  输出：结构化条款列表 [{编号, 标题, 内容, 层级}]
  工具：LLM 结构化提取 + 正则规则辅助

Step 3: 知识库检索
  输入：每个条款的文本
  输出：每个条款匹配到的相关规则（Top 5）
  工具：Embedding 语义检索 + 关键词匹配

Step 4: 逐条风险分析（可并行）
  输入：条款 + 合同类型 + 知识库规则 + 合同上下文
  输出：{风险等级, 风险类型, 通俗解释, 法律依据}
  工具：LLM 分析

Step 5: 修改建议生成
  输入：红色/黄色条款 + 原文
  输出：{建议修改后的措辞, 修改理由, 是否可谈判}
  工具：LLM 生成

Step 6: 综合评分
  输入：所有条款分析结果
  输出：{总分, 风险分布, 一句话总结, 建议（签/改/拒）}
  工具：LLM 综合判断

Step 7: 知识库回馈
  输入：本次分析中发现的新风险模式
  操作：标记为待审核，纳入知识库进化候选
```

#### 2.2 Harness 容错

- 每步失败最多重试 2 次
- Step 4 单条失败不影响其他条款
- LLM 输出格式错误时自动触发格式修复
- 全部失败时返回错误提示 + 已完成的部分结果

#### 2.3 Prompt 工程（分层体系）

**Layer 0 — System Prompt**：
```
你是一个专业的合同风险审查助手。你的工作是：
1. 逐条审查合同条款
2. 识别不利于签署方（默认为合同中的"乙方"，即接受方）的条款
3. 用通俗易懂的语言解释风险
4. 给出具体的修改建议

约束：
- 你不是律师，不提供法律意见，只做风险提示
- 不确定的条款标记为"建议咨询专业人士"
- 输出必须严格遵循指定的 JSON 格式
```

**Layer 1 — 分类 Prompt**：
```
分析以下合同文本，判断其合同类型。
可选类型：租赁合同、劳动合同、装修合同、外包合同、借款合同、服务合同、采购合同、合作协议、其他
仅返回类型名称。
```

**Layer 2 — 条款拆解 Prompt**：
```
将以下合同拆解为独立条款，返回 JSON 数组：
[{clause_number, title, content, level}]
```

**Layer 3 — 风险分析 Prompt（核心）**：
```
审查一份{合同类型}。分析以下条款的风险：
条款：{clause_content}
相关知识库规则：{kb_rules}

返回 JSON：
{
  "risk_level": "red" | "yellow" | "green",
  "risk_type": "...",
  "risk_summary": "一句话（20字内）",
  "plain_explanation": "大白话（50字内）",
  "legal_basis": "法律依据",
  "severity_score": 1-10
}
```

**Layer 4 — 修改建议 Prompt**：
```
针对以下风险条款，生成修改建议：
条款：{clause}
风险：{risk_type}

返回 JSON：
{
  "suggested_clause": "修改后的完整条款",
  "modification_reason": "理由（30字内）",
  "can_negotiate": true/false,
  "negotiation_tip": "谈判话术"
}
```

**Layer 5 — 综合评分 Prompt**：
```
基于以下分析结果，给出综合评分：
{all_analyses}

返回 JSON：
{
  "overall_score": 0-100,
  "risk_distribution": {"red": N, "yellow": N, "green": N},
  "top_risks": ["最危险的3个风险"],
  "one_line_summary": "一句话总结",
  "recommendation": "sign" | "negotiate_first" | "reject"
}
```

### 模块 3：自进化知识库

#### 3.1 知识库结构

```
知识库
├── 基础规则库（手动维护）
│   ├── 通用合同风险规则（50+ 条）
│   ├── 租赁合同专项规则（20+ 条）
│   ├── 劳动合同专项规则（20+ 条）
│   └── ...
│
├── 法规库（定期更新）
│   ├── 民法典相关条款
│   ├── 劳动合同法
│   └── ...
│
├── 案例库（自动积累）
│   ├── 用户确认正确的分析 → 强化规则
│   ├── 用户标记错误的分析 → 修正规则
│   └── 新风险模式 → 审核后入库
│
└── 行业惯例库（自动学习）
    └── 从大量分析中提炼的常见模式
```

#### 3.2 自进化机制

```
分析合同 → 用户反馈 → 反馈入库
                         ↓
              自动学习 pipeline
              ├── 聚类相似反馈
              ├── 提炼新规则候选
              ├── 与现有规则去重
              ├── 计算置信度
              ├── 高置信（>0.8）→ 自动入库
              └── 低置信（<0.8）→ 人工审核
                         ↓
                    规则库更新
                         ↓
              下次分析时检索新规则
```

#### 3.3 知识检索策略

1. **关键词匹配**：条款中出现"违约金" → 检索所有违约金相关规则
2. **合同类型过滤**：租赁合同只检索租赁专项 + 通用规则
3. **Embedding 语义检索**：用 embedding 向量找语义最接近的规则（Top 5）
4. **规则优先级**：高置信度规则优先

### 模块 4：数据存储

#### 4.1 SQLite 数据表

```sql
-- 合同主表
CREATE TABLE contracts (
    id            TEXT PRIMARY KEY,     -- UUID
    title         TEXT,                 -- 合同标题
    type          TEXT,                 -- 合同类型
    source_file   TEXT,                 -- 原始文件路径
    ocr_text      TEXT,                 -- OCR 识别全文
    ocr_raw       TEXT,                 -- OCR 结构化数据（JSON）
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 分析结果表
CREATE TABLE analyses (
    id              TEXT PRIMARY KEY,
    contract_id     TEXT REFERENCES contracts(id),
    model_used      TEXT,               -- 使用的模型
    overall_score   INTEGER,            -- 总分 0-100
    summary         TEXT,               -- 一句话总结
    recommendation  TEXT,               -- sign/negotiate_first/reject
    raw_result      TEXT,               -- 完整结果（JSON）
    source          TEXT,               -- 'local' | 'cloud' | 'remote_pc'
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 条款分析表
CREATE TABLE clause_analyses (
    id                TEXT PRIMARY KEY,
    analysis_id       TEXT REFERENCES analyses(id),
    clause_number     TEXT,
    clause_title      TEXT,
    clause_content    TEXT,
    risk_level        TEXT,             -- red/yellow/green
    risk_type         TEXT,
    risk_summary      TEXT,
    plain_explanation TEXT,
    legal_basis       TEXT,
    severity_score    INTEGER,
    suggested_clause  TEXT,
    can_negotiate     BOOLEAN,
    user_feedback     TEXT,             -- correct/incorrect/none
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 知识库规则表
CREATE TABLE knowledge_rules (
    id              TEXT PRIMARY KEY,
    category        TEXT,               -- 通用/租赁/劳动/装修/...
    rule_text       TEXT,               -- 规则描述
    trigger_keywords TEXT,              -- 触发关键词（JSON 数组）
    embedding       BLOB,              -- 向量（可选）
    confidence      REAL DEFAULT 0.5,  -- 置信度 0-1
    source          TEXT,              -- manual/auto_learned/user_feedback
    usage_count     INTEGER DEFAULT 0,
    confirm_count   INTEGER DEFAULT 0,
    reject_count    INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 法规条文表
CREATE TABLE legal_references (
    id              TEXT PRIMARY KEY,
    law_name        TEXT,
    article_number  TEXT,
    content         TEXT,
    effective_date  DATE,
    tags            TEXT                -- JSON 数组
);

-- 同步日志
CREATE TABLE sync_log (
    id              TEXT PRIMARY KEY,
    sync_type       TEXT,               -- webdav/git/s3
    direction       TEXT,               -- push/pull
    status          TEXT,               -- success/failed
    details         TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 模块 5：云同步

| 方式 | 库 | 说明 |
|------|---|------|
| WebDAV | webdavclient3 | 支持坚果云、NextCloud |
| Git | subprocess | 整个数据目录作为 Git 仓库 |
| S3 | boto3 | 支持 MinIO、阿里 OSS、腾讯 COS |

**同步规则**：
- 默认仅本地，需用户主动开启
- 同步前自动备份
- 冲突以时间戳最新为准
- 合同原文件（图片/PDF）默认不同步（体积大）

### 模块 6：前端界面

#### 6.1 电脑端管理面板

```
首页（仪表盘）
├── 最近分析（列表 + 评分）
├── 风险分布统计
└── 快速上传入口

合同管理
├── 合同列表（搜索、筛选、排序）
├── 合同详情页（分析结果 + 历史版本）
└── 批量分析

知识库管理
├── 规则列表（按类型分组、搜索）
├── 添加/编辑/删除规则
├── 法规库管理
├── 规则审核（待审核的新规则）
└── 知识库统计

同步管理
├── 同步配置（WebDAV/Git/S3）
├── 同步状态
└── 手动同步

设置
├── LLM 配置（API Key、模型、Ollama 地址）
├── 数据管理（导出、备份、清理）
├── 客户端连接（查看连接的手机）
└── 关于
```

#### 6.2 手机端界面

```
首页
├── 拍照 / 选择文件（大按钮）
├── 连接状态（已连接电脑 / 使用云端 API）
└── 最近分析列表

分析中（加载页）
├── 正在识别文字... (Step 1/6)
├── 正在拆解条款... (Step 2/6)
├── 正在检索知识库... (Step 3/6)
├── 正在分析风险... (Step 4/6)
└── 逐条实时出现结果

分析结果页
├── 总览卡片（分数 + 风险分布 + 一句话）
├── 条款列表（红黄绿标签）
│   ├── 条款原文（高亮风险语句）
│   ├── 通俗解释
│   ├── 风险类型
│   ├── 修改建议（一键复制）
│   └── 反馈按钮（对/错）
└── 操作栏（分享报告 / 重新分析）

历史记录
└── 以前分析过的合同列表
```

---

## 七、MVP 分期

### P0 — 核心可用

- [ ] 电脑端：FastAPI 后端 + SQLite + PaddleOCR-VL
- [ ] 电脑端：Agent Harness 完整流程（6 步）
- [ ] 电脑端：LLM 网关（OpenAI 标准 + Ollama）
- [ ] 电脑端：基础 Web 管理面板（合同列表 + 分析结果展示）
- [ ] 手机端：PWA（拍照上传 + 结果展示）
- [ ] 手机端：通过 WebSocket 连接电脑端
- [ ] 分析结果存储（SQLite）
- [ ] 基础规则库（50+ 通用规则）

### P1 — 知识库 + 独立模式

- [ ] Embedding 本地检索（sentence-transformers / Transformers.js）
- [ ] 知识库管理界面（增删改查）
- [ ] 用户反馈机制
- [ ] 知识库自动进化 pipeline
- [ ] 手机端独立模式（直连云端 API，不经过电脑）
- [ ] 法规库（民法典 + 劳动合同法）

### P2 — 同步 + 优化

- [ ] WebDAV 同步
- [ ] Git 同步
- [ ] S3 同步
- [ ] 数据导出（Markdown / PDF 报告）
- [ ] 合同原文件管理
- [ ] Docker 一键部署

### P3 — 增强

- [ ] 合同模板库
- [ ] 多合同对比
- [ ] 合同版本 diff
- [ ] 知识库社区贡献机制
- [ ] 内网穿透（在外面远程连接家里电脑）

---

## 八、非功能需求

| 项目 | 要求 |
|------|------|
| Python 版本 | >= 3.10 |
| 前端 | 无框架依赖，纯 HTML/CSS/JS |
| 数据库 | SQLite，零配置 |
| OCR | PaddleOCR-VL，本地运行 |
| LLM | OpenAI 兼容 API（远程或本地 Ollama） |
| 部署 | 单机运行，Docker 可选 |
| 隐私 | 数据默认不离开本地 |
| 性能 | 单份合同分析 < 60 秒 |
| 离线 | OCR + 规则引擎可完全离线 |
| 兼容性 | 电脑端支持 Win/Mac/Linux；手机端支持 iOS/Android 浏览器 |

---

## 九、开源计划

- **协议**：MIT License
- **仓库**：clause-light（GitHub）
- **语言**：README 中文 + English
- **文档**：PRD + 贡献指南 + 知识库贡献规范
- **社区**：接受规则贡献、bug 报告、功能建议
