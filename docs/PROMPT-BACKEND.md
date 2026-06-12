# ClauseLight 后端开发提示词

## 任务

实现 ClauseLight 电脑端后端服务。当前所有后端 Python 文件为空，需要从零实现。

## 开发顺序（严格按此顺序，每次只做一个 Phase）

```
Phase 1: 基础设施
  1.1 config.py — 配置管理
  1.2 database.py — 数据库模型 + 初始化
  1.3 llm.py — LLM 网关
  1.4 prompts/ — Prompt 模板

Phase 2: 核心引擎
  2.1 ocr.py — OCR 封装
  2.2 knowledge.py — 知识库引擎
  2.3 agent.py — Agent Harness（7 步分析流程）

Phase 3: API 层
  3.1 contracts.py — 合同分析接口
  3.2 knowledge.py — 知识库接口
  3.3 sync.py — 同步接口
  3.4 ws.py — WebSocket 接口
  3.5 main.py — FastAPI 主入口 + 静态文件挂载

Phase 4: 脚本
  4.1 scripts/init_db.py — 数据库初始化
  4.2 scripts/import_rules.py — 基础规则导入
```

## 技术约束（必须遵守）

- Python >= 3.10，全部使用 type hints
- Web 框架：FastAPI + uvicorn
- 数据库：SQLite（通过 SQLAlchemy async ORM，不写裸 SQL）
- LLM 调用：必须通过 `server/core/llm.py` 统一网关，不能直接调 openai SDK
- Prompt 模板：必须存放在 `server/core/prompts/` 目录
- 日志：使用 `logging` 模块，不能用 print()
- 异常：必须处理，不能有裸 except
- API Key：从环境变量读取，不能硬编码
- 所有 API 返回 JSON
- 每个 Phase 完成后可以独立运行

## Phase 1.1 — 配置管理（server/config.py）

使用 Pydantic Settings，支持 .env 文件和环境变量。

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 服务
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///data/clause_light.db"

    # 文件存储
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB

    # LLM — 远程 API
    LLM_DEEPSEEK_API_KEY: str = ""
    LLM_OPENAI_API_KEY: str = ""
    LLM_QWEN_API_KEY: str = ""

    # LLM — 本地 Ollama
    OLLAMA_ENDPOINT: str = "http://localhost:11434"

    # OCR
    OCR_USE_GPU: bool = False

    # 同步
    SYNC_ENABLED: bool = False
    WEBDAV_URL: str = ""
    WEBDAV_USERNAME: str = ""
    WEBDAV_PASSWORD: str = ""
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

全局单例通过 `from server.config import settings` 导入。

## Phase 1.2 — 数据库模型（server/models/database.py）

使用 SQLAlchemy 2.0 async 风格。5 张核心表：

### contracts 表
```sql
id TEXT PRIMARY KEY          -- UUID
title TEXT                   -- 合同标题
type TEXT                    -- 合同类型（租赁/劳动/装修/外包/借款/服务/其他）
source_file TEXT             -- 原始文件路径
ocr_text TEXT                -- OCR 识别全文
ocr_raw TEXT                 -- OCR 结构化数据（JSON 字符串）
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### analyses 表
```sql
id TEXT PRIMARY KEY
contract_id TEXT REFERENCES contracts(id)
model_used TEXT              -- 使用的模型名
overall_score INTEGER        -- 总分 0-100
summary TEXT                 -- 一句话总结
recommendation TEXT          -- sign / negotiate_first / reject
raw_result TEXT              -- 完整结果（JSON 字符串）
source TEXT                  -- local / cloud / remote_pc
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### clause_analyses 表
```sql
id TEXT PRIMARY KEY
analysis_id TEXT REFERENCES analyses(id)
clause_number TEXT           -- 条款编号（第三条）
clause_title TEXT            -- 条款标题
clause_content TEXT          -- 条款原文
risk_level TEXT              -- red / yellow / green
risk_type TEXT               -- 风险类型
risk_summary TEXT            -- 一句话摘要
plain_explanation TEXT       -- 通俗解释
legal_basis TEXT             -- 法律依据
severity_score INTEGER       -- 1-10
suggested_clause TEXT        -- 修改建议
can_negotiate BOOLEAN        -- 是否可谈判
user_feedback TEXT           -- correct / incorrect / null
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### knowledge_rules 表
```sql
id TEXT PRIMARY KEY
category TEXT                -- 通用/租赁/劳动/装修/外包/借款/服务/采购/合作/其他
rule_text TEXT               -- 规则描述
trigger_keywords TEXT        -- 触发关键词（JSON 字符串）
embedding BLOB               -- 向量（可选，暂不实现）
confidence REAL DEFAULT 0.5  -- 置信度 0-1
source TEXT                  -- manual / auto_learned / user_feedback
usage_count INTEGER DEFAULT 0
confirm_count INTEGER DEFAULT 0
reject_count INTEGER DEFAULT 0
is_active BOOLEAN DEFAULT 1
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### legal_references 表
```sql
id TEXT PRIMARY KEY
law_name TEXT                -- 法规名称
article_number TEXT          -- 条文编号
content TEXT                 -- 条文内容
effective_date DATE
tags TEXT                    -- 标签（JSON 字符串）
```

### sync_log 表
```sql
id TEXT PRIMARY KEY
sync_type TEXT               -- webdav / git / s3
direction TEXT               -- push / pull
status TEXT                  -- success / failed
details TEXT
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

需要提供：
- `AsyncSession` 工厂函数
- `init_db()` 函数（创建所有表）
- `get_db()` 依赖注入函数（用于 FastAPI Depends）

## Phase 1.3 — LLM 网关（server/core/llm.py）

统一的 LLM 调用层，所有 LLM 交互必须通过此模块。

```python
class LLMGateway:
    """LLM 统一网关，支持多提供商、多模型、故障切换"""

    def __init__(self):
        # 根据 settings 初始化 openai AsyncClient
        # 支持 DeepSeek / OpenAI / 通义千问 / Ollama

    async def chat(
        self,
        messages: list[dict],
        task: str,  # classification / analysis / explanation / scoring
        temperature: float = 0.1,
        max_retries: int = 2
    ) -> LLMResponse:
        """
        1. 根据 task 选择对应的模型配置
           - classification → 小模型（便宜、快）
           - analysis → 大模型（准确）
           - explanation → 小模型（通俗易懂）
           - scoring → 大模型（综合判断）
        2. 调用 LLM API
        3. 失败时自动重试 + 切换备用模型
        4. 返回结构化响应
        """

    async def chat_stream(
        self,
        messages: list[dict],
        task: str,
        temperature: float = 0.1
    ) -> AsyncGenerator[str, None]:
        """流式输出，用于 WebSocket 实时推送"""

class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_used: int
    latency_ms: int
```

**故障切换逻辑**：
```
主模型失败 → 重试（换 temperature）→ 再失败 → 切换备用模型 → 再失败 → 返回错误
```

**模型路由配置**（硬编码在 llm.py 中，后续可改为配置文件）：
```python
TASK_MODEL_MAP = {
    "deepseek": {
        "classification": "deepseek-chat",
        "analysis": "deepseek-chat",
        "explanation": "deepseek-chat",
        "scoring": "deepseek-chat",
    },
    "openai": {
        "classification": "gpt-4o-mini",
        "analysis": "gpt-4o",
        "explanation": "gpt-4o-mini",
        "scoring": "gpt-4o",
    },
}
```

## Phase 1.4 — Prompt 模板（server/core/prompts/）

每个 prompt 模板是一个 Python 函数，接收参数返回 messages 列表。

### prompts/classify.py
```python
def classify_prompt(contract_text: str) -> list[dict]:
    """合同分类 prompt"""
    return [
        {"role": "system", "content": "你是一个合同分类专家。分析以下合同文本，判断其合同类型。\n可选类型：租赁合同、劳动合同、装修合同、外包合同、借款合同、服务合同、采购合同、合作协议、其他\n仅返回类型名称，不要其他内容。"},
        {"role": "user", "content": f"分析以下合同的类型：\n\n{contract_text[:3000]}"}
    ]
```

### prompts/split.py
```python
def split_prompt(contract_text: str, contract_type: str) -> list[dict]:
    """条款拆解 prompt"""
    return [
        {"role": "system", "content": "你是一个合同条款拆解专家。将以下合同拆解为独立条款，返回 JSON 数组。\n每个元素包含：clause_number（条款编号）、title（条款标题）、content（条款内容）\n仅返回 JSON 数组，不要其他内容。"},
        {"role": "user", "content": f"合同类型：{contract_type}\n\n合同全文：\n{contract_text}"}
    ]
```

### prompts/analyze.py
```python
def analyze_prompt(
    clause_content: str,
    contract_type: str,
    contract_context: str,
    kb_rules: list[str]
) -> list[dict]:
    """风险分析 prompt（核心）"""
    rules_text = "\n".join(f"- {r}" for r in kb_rules) if kb_rules else "无相关规则"
    return [
        {"role": "system", "content": """你是一个专业的合同风险审查助手。分析以下条款的风险。
默认从接受方（乙方）的角度审查。

返回 JSON：
{
  "risk_level": "red" | "yellow" | "green",
  "risk_type": "风险类型（如：违约金过高、霸王条款、权责不对等等）",
  "risk_summary": "一句话摘要（20字内）",
  "plain_explanation": "大白话解释（50字内）",
  "legal_basis": "相关法律依据",
  "severity_score": 1-10
}"""},
        {"role": "user", "content": f"合同类型：{contract_type}\n\n条款内容：{clause_content}\n\n相关知识库规则：{rules_text}"}
    ]
```

### prompts/suggest.py
```python
def suggest_prompt(clause: str, risk_type: str) -> list[dict]:
    """修改建议 prompt"""
    return [
        {"role": "system", "content": """针对以下风险条款，生成修改建议。

返回 JSON：
{
  "suggested_clause": "修改后的完整条款",
  "modification_reason": "理由（30字内）",
  "can_negotiate": true/false,
  "negotiation_tip": "谈判话术（如有）"
}"""},
        {"role": "user", "content": f"条款：{clause}\n风险类型：{risk_type}"}
    ]
```

### prompts/score.py
```python
def score_prompt(all_analyses: list[dict]) -> list[dict]:
    """综合评分 prompt"""
    analyses_text = "\n\n".join([
        f"条款：{a.get('clause_number', '')} {a.get('clause_title', '')}\n"
        f"风险：{a.get('risk_level', '')} - {a.get('risk_summary', '')}\n"
        f"评分：{a.get('severity_score', 0)}"
        for a in all_analyses
    ])
    return [
        {"role": "system", "content": """基于以下分析结果，给出综合评分。

返回 JSON：
{
  "overall_score": 0-100,
  "risk_distribution": {"red": N, "yellow": N, "green": N},
  "top_risks": ["最危险的3个风险"],
  "one_line_summary": "一句话总结",
  "recommendation": "sign" | "negotiate_first" | "reject"
}"""},
        {"role": "user", "content": f"分析结果：\n{analyses_text}"}
    ]
```

## Phase 2.1 — OCR 封装（server/core/ocr.py）

```python
class OCREngine:
    """PaddleOCR 封装"""

    def __init__(self):
        # 延迟导入 paddleocr（首次调用时才加载模型）
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=settings.OCR_USE_GPU)
        return self._ocr

    async def recognize(self, file_path: str) -> OCRResult:
        """
        1. 读取文件（图片或 PDF）
        2. 如果是 PDF，用 PyMuPDF 逐页提取图片
        3. 调用 PaddleOCR 识别
        4. 整合文本结构
        """

class OCRResult:
    full_text: str          # 完整拼接文本
    pages: list[dict]       # 分页结果
    confidence_avg: float   # 平均置信度
```

## Phase 2.2 — 知识库引擎（server/core/knowledge.py）

```python
class KnowledgeEngine:
    """知识库管理与检索"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        query: str,
        contract_type: str,
        top_k: int = 5
    ) -> list[dict]:
        """
        1. 从 knowledge_rules 表查询 is_active=1 的规则
        2. 按 category 过滤（通用 + 对应合同类型）
        3. 关键词匹配（rule_text 中包含 query 的关键词）
        4. 按 confidence 降序排序
        5. 返回 Top K
        """

    async def add_rule(self, rule_data: dict) -> dict:
        """新增规则"""

    async def update_rule(self, rule_id: str, data: dict) -> None:
        """更新规则"""

    async def delete_rule(self, rule_id: str) -> None:
        """删除规则"""

    async def get_stats(self) -> dict:
        """知识库统计：规则总数、各分类数量、平均置信度等"""

    async def get_pending(self) -> list[dict]:
        """获取待审核规则"""

    async def get_laws(self) -> list[dict]:
        """获取法规列表"""
```

## Phase 2.3 — Agent Harness（server/core/agent.py）

7 步分析流程，每步失败最多重试 2 次。

```python
class ContractAgent:
    """合同分析 Agent"""

    def __init__(self, llm: LLMGateway, knowledge: KnowledgeEngine, ocr: OCREngine):
        self.llm = llm
        self.knowledge = knowledge
        self.ocr = ocr

    async def analyze(
        self,
        file_path: str,
        contract_type_hint: str | None = None,
        on_step: Callable | None = None  # 进度回调
    ) -> AnalysisResult:
        """完整的 7 步分析流程"""

        # Step 1: OCR 识别
        # Step 2: 合同分类（LLM）
        # Step 3: 条款拆解（LLM）
        # Step 4: 知识库检索
        # Step 5: 逐条风险分析（LLM，并行）
        # Step 6: 修改建议生成（LLM）
        # Step 7: 综合评分（LLM）

class AnalysisResult:
    contract_id: str
    contract_type: str
    overall_score: int
    recommendation: str
    summary: str
    clauses: list[dict]  # 每条含 risk_level, risk_summary, plain_explanation, suggested_clause 等
```

**容错策略**：
- 每步失败最多重试 2 次
- Step 5 单条失败不影响其他条款
- LLM 输出格式错误时尝试 JSON 修复
- 全部失败时返回错误 + 已完成的部分结果

## Phase 3 — API 层

### 3.1 合同接口（server/api/contracts.py）

```python
router = APIRouter(prefix="/api/contracts", tags=["contracts"])

@router.get("/")                           # GET /api/contracts
@router.get("/{contract_id}")              # GET /api/contracts/{id}
@router.post("/analyze")                   # POST /api/contracts/analyze
@router.post("/{contract_id}/feedback")    # POST /api/contracts/{id}/feedback
```

**GET /api/contracts** 支持 query 参数：`search`, `type`, `risk`
返回格式（匹配前端 api.js 中 MOCK_CONTRACTS 的结构）：
```json
[{
  "id": "xxx",
  "title": "房屋租赁合同",
  "type": "租赁合同",
  "typeEn": "rental",
  "score": 42,
  "riskLevel": "red",
  "redCount": 5,
  "yellowCount": 3,
  "greenCount": 2,
  "createdAt": "2026-06-10",
  "status": "analyzed",
  "model": "deepseek-chat"
}]
```

**POST /api/contracts/analyze** — multipart/form-data，字段 `file` + 可选 `contract_type`

### 3.2 知识库接口（server/api/knowledge.py）

```python
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

@router.get("/rules")                      # GET /api/knowledge/rules
@router.post("/rules")                     # POST /api/knowledge/rules
@router.put("/rules/{rule_id}")            # PUT /api/knowledge/rules/{id}
@router.delete("/rules/{rule_id}")         # DELETE /api/knowledge/rules/{id}
@router.get("/stats")                      # GET /api/knowledge/stats
@router.get("/pending")                    # GET /api/knowledge/pending
@router.get("/laws")                       # GET /api/knowledge/laws
@router.post("/pending/{id}/approve")      # POST /api/knowledge/pending/{id}/approve
@router.post("/pending/{id}/reject")       # POST /api/knowledge/pending/{id}/reject
```

### 3.3 同步接口（server/api/sync.py）

```python
router = APIRouter(prefix="/api/sync", tags=["sync"])

@router.get("/config")                     # GET /api/sync/config
@router.put("/config")                     # PUT /api/sync/config
@router.post("/push")                      # POST /api/sync/push
@router.post("/pull")                      # POST /api/sync/pull
@router.get("/log")                        # GET /api/sync/log
```

### 3.4 WebSocket（server/api/ws.py）

```python
# /ws/client — 手机端连接
# 接收：合同文本 + 分析请求
# 发送：分析进度（逐 step）、分析结果（逐条）
# 支持断线重连
```

### 3.5 FastAPI 主入口（server/main.py）

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ClauseLight", version="1.0.0")

# 注册路由
app.include_router(contracts_router)
app.include_router(knowledge_router)
app.include_router(sync_router)

# 挂载静态文件（前端管理面板）
app.mount("/admin", StaticFiles(directory="server/static", html=True), name="admin")

# 挂载手机端
app.mount("/mobile", StaticFiles(directory="mobile", html=True), name="mobile")

# 启动时初始化数据库
@app.on_event("startup")
async def startup():
    await init_db()

# GET / → 重定向到 /admin/
```

启动命令：`python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload`

## Phase 4 — 脚本

### scripts/init_db.py
```python
"""初始化数据库，创建所有表"""
import asyncio
from server.models.database import init_db
asyncio.run(init_db())
print("数据库初始化完成")
```

### scripts/import_rules.py
```python
"""导入基础规则库（50+ 条通用规则）"""
# 从 shared/rules/*.json 读取规则，导入 knowledge_rules 表
# 通用规则 20+ 条，租赁 10+ 条，劳动 10+ 条，装修/外包各 5+ 条
```

同时需要创建 `shared/rules/general.json`、`shared/rules/rental.json`、`shared/rules/labor.json` 等文件，每条规则格式：
```json
{
  "category": "通用",
  "rule_text": "滞纳金或违约金超过合同金额20%的条款应标记为高风险",
  "trigger_keywords": ["违约金", "滞纳金", "赔偿"],
  "confidence": 0.9,
  "source": "manual"
}
```

## 前端对接

前端 `api.js` 中 `USE_MOCK = true`，后端完成后需要：

1. 将 `USE_MOCK` 改为 `false`
2. 确保所有 API 返回格式与前端 MOCK 数据结构一致
3. 测试所有页面的数据流

## 验证标准

完成后需要检查：
- [ ] `python -m uvicorn server.main:app` 能正常启动
- [ ] `http://localhost:8080/admin/` 能加载前端页面
- [ ] `GET /api/contracts` 返回 JSON 数组
- [ ] `POST /api/contracts/analyze` 能上传文件并返回分析结果
- [ ] `GET /api/knowledge/rules` 返回规则列表
- [ ] `POST /api/knowledge/rules` 能新增规则
- [ ] `GET /api/knowledge/stats` 返回统计数据
- [ ] `GET /api/sync/config` 返回同步配置
- [ ] 所有 API 返回格式与前端 api.js 中 MOCK 数据结构一致
- [ ] 没有裸 except、没有 print()、没有硬编码 API Key
- [ ] 所有 Python 文件使用 type hints