# TECHNICAL.md — ClauseLight 技术方案

## 一、项目配置与基础设施

### 1.1 配置管理（server/config.py）

使用 Pydantic Settings 管理所有配置，支持环境变量和 .env 文件。

```python
# 核心配置项
class Settings:
    # 服务
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "sqlite:///data/clause_light.db"

    # 文件存储
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB

    # LLM - 远程 API
    LLM_DEFAULT_PROVIDER: str = "deepseek"
    LLM_PROVIDERS: dict = {
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",  # 从环境变量 LLM_DEEPSEEK_API_KEY 读取
            "models": {
                "classification": "deepseek-chat",
                "analysis": "deepseek-chat",
                "explanation": "deepseek-chat"
            }
        }
    }

    # LLM - 本地 Ollama
    OLLAMA_ENDPOINT: str = "http://localhost:11434"
    OLLAMA_MODELS: dict = {
        "classification": "qwen2.5:7b",
        "analysis": "qwen2.5:32b",
        "explanation": "qwen2.5:7b"
    }

    # OCR
    OCR_LANGUAGE: str = "ch"  # 中文
    OCR_USE_GPU: bool = False

    # Embedding
    EMBEDDING_MODEL: str = "shibing624/text2vec-base-chinese"
    EMBEDDING_DIMENSION: int = 768

    # 同步
    SYNC_ENABLED: bool = False
    WEBDAV_URL: str = ""
    WEBDAV_USERNAME: str = ""
    WEBDAV_PASSWORD: str = ""
```

### 1.2 数据库模型（server/models/database.py）

使用 SQLAlchemy 2.0 async 风格。

```python
# 五张核心表
# contracts      - 合同主表
# analyses       - 分析结果表
# clause_analyses - 条款分析表
# knowledge_rules - 知识库规则表
# legal_references - 法规条文表
# sync_log       - 同步日志表
```

详细表结构见 PRD 第六章 4.1 节。

### 1.3 ContractOps 2.0 M0 运行拓扑

开发环境保留 SQLite 兼容 v1；M0 的 Docker Compose 使用 PostgreSQL 16、Redis 7、API 和独立 Worker。PostgreSQL 是合同、版本、任务、Outbox、租户和审计的事实来源；Redis 只承载限流、进度广播等可重建状态，断开时按配置降级，不取代数据库。Kafka 不属于 M0 运行依赖。

迁移由 Alembic 执行，容器先等待 PostgreSQL 健康，再运行 `migrate`，API/Worker 依赖迁移成功后启动：

```powershell
docker compose -f docker/docker-compose.yml up --build -d
docker compose -f docker/docker-compose.yml run --rm migrate
python scripts/verify_m0.py
python scripts/import_v1_sqlite.py --source data/clause_light.db --dry-run
```

v1 导入前应复制 `data/clause_light.db` 并保存 SHA-256；`scripts/import_v1_sqlite.py` 以只读方式打开源库，dry-run 和正式导入均输出计数守恒报告。回滚时停止 M0 服务、恢复备份 SQLite，并执行 `git switch main` 后按 v1 启动命令运行。M0 的 `verify_m0.py` 输出迁移耗时、任务状态、审计计数、重复副作用和隐私违规计数，便于形成交付数据。

### 1.3 LLM 网关（server/core/llm.py）

统一的 LLM 调用层，所有 LLM 交互必须通过此模块。

```python
class LLMGateway:
    """LLM 统一网关，支持多提供商、多模型、故障切换"""

    async def chat(
        self,
        messages: list[dict],
        task: str,           # classification / analysis / explanation / scoring
        temperature: float = 0.1,
        max_retries: int = 2
    ) -> LLMResponse:
        """
        1. 根据 task 选择对应的模型配置
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
    from_cache: bool
```

**故障切换逻辑**：
```
主模型失败 → 重试（换 temperature）→ 再失败 → 切换备用模型 → 再失败 → 返回错误
```

### 1.4 Prompt 模板（server/core/prompts/）

每个 prompt 模板是一个 Python 函数，接收参数返回 messages 列表。

```python
# prompts/classify.py
def classify_prompt(contract_text: str) -> list[dict]:
    return [
        {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
        {"role": "user", "content": f"分析以下合同类型：\n\n{contract_text[:3000]}"}
    ]

# prompts/analyze.py
def analyze_prompt(
    clause_content: str,
    contract_type: str,
    contract_context: str,
    kb_rules: list[str]
) -> list[dict]:
    rules_text = "\n".join(f"- {r}" for r in kb_rules) if kb_rules else "无相关规则"
    return [
        {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
        {"role": "user", "content": ANALYZE_USER_TEMPLATE.format(
            contract_type=contract_type,
            clause_content=clause_content,
            contract_context=contract_context,
            kb_rules=rules_text
        )}
    ]
```

---

## 二、Agent Harness（server/core/agent.py）

### 2.1 流程定义

```python
class ContractAgent:
    """合同分析 Agent，编排完整的分析流程"""

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
        ocr_result = await self._step_ocr(file_path)
        if on_step: await on_step("ocr_done", ocr_result)

        # Step 2: 合同分类
        contract_type = await self._step_classify(ocr_result.full_text, contract_type_hint)
        if on_step: await on_step("classified", contract_type)

        # Step 3: 条款拆解
        clauses = await self._step_split(ocr_result.full_text, contract_type)
        if on_step: await on_step("split", clauses)

        # Step 4: 知识库检索
        kb_results = await self._step_retrieve(clauses, contract_type)
        if on_step: await on_step("retrieved", kb_results)

        # Step 5: 逐条风险分析（可并行）
        clause_analyses = await self._step_analyze(clauses, contract_type, kb_results)
        if on_step: await on_step("analyzed", clause_analyses)

        # Step 6: 修改建议生成
        suggestions = await self._step_suggest(clause_analyses)
        if on_step: await on_step("suggested", suggestions)

        # Step 7: 综合评分
        final_score = await self._step_score(clause_analyses)
        if on_step: await on_step("scored", final_score)

        return AnalysisResult(
            contract_type=contract_type,
            clauses=clauses,
            analyses=clause_analyses,
            suggestions=suggestions,
            score=final_score
        )
```

### 2.2 容错策略

```python
async def _safe_step(self, step_func, fallback, step_name: str):
    """每步安全执行，失败时重试 + 降级"""
    for attempt in range(3):
        try:
            return await step_func()
        except LLMRateLimitError:
            await asyncio.sleep(2 ** attempt)
        except LLMFormatError as e:
            logger.warning("LLM 输出格式异常，重试: step=%s attempt=%d", step_name, attempt)
        except Exception as e:
            logger.error("步骤失败: step=%s error=%s", step_name, e)
            break

    # 所有重试失败，使用降级方案
    return await fallback()
```

### 2.3 手机端 vs 电脑端的 Agent 差异

| 功能 | 电脑端 | 手机端 |
|------|--------|--------|
| OCR | PaddleOCR-VL 本地 | 发送给电脑端 API |
| Agent Harness | 完整 7 步 | 精简版（跳过 OCR 步骤） |
| LLM 调用 | 直接调用 | 通过电脑端代理 或 直连云端 |
| 知识库检索 | 本地 Embedding | 通过电脑端 或 本地 Transformers.js |
| 结果存储 | SQLite 本地 | IndexedDB + 电脑端同步 |

---

## 三、OCR 引擎（server/core/ocr.py）

```python
class OCREngine:
    """PaddleOCR-VL 封装"""

    def __init__(self, use_gpu: bool = False, lang: str = "ch"):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu)

    async def recognize(self, file_path: str) -> OCRResult:
        """
        1. 读取文件（图片或 PDF）
        2. 如果是 PDF，逐页提取图片
        3. 调用 PaddleOCR 识别
        4. 整合文本结构（段落、条款层级）
        """

class OCRResult:
    full_text: str              # 完整拼接文本
    pages: list[PageResult]     # 分页结果
    structure: list[Clause]     # 结构化条款
    confidence_avg: float       # 平均置信度

class PageResult:
    page_number: int
    text_blocks: list[TextBlock]

class TextBlock:
    text: str
    bbox: list[float]
    confidence: float
```

---

## 四、知识库引擎（server/core/knowledge.py）

```python
class KnowledgeEngine:
    """知识库管理与检索"""

    def __init__(self, db: AsyncSession, embedding_model: str):
        self.db = db
        self.embedder = SentenceTransformer(embedding_model)
        self._rules_cache: list[Rule] | None = None

    async def search(
        self,
        query: str,
        contract_type: str,
        top_k: int = 5
    ) -> list[Rule]:
        """
        1. 关键词匹配
        2. 合同类型过滤
        3. Embedding 语义检索
        4. 合并去重，按置信度排序
        5. 返回 Top K
        """

    async def add_rule(self, rule: RuleCreate) -> Rule:
        """新增规则"""

    async def update_from_feedback(
        self,
        clause_id: str,
        feedback: str  # "correct" | "incorrect"
    ) -> None:
        """根据用户反馈更新规则置信度"""

    async def evolve(self) -> list[Rule]:
        """知识库自动进化：聚类反馈、提炼新规则"""
```

---

## 五、API 层

### 5.1 合同分析 API（server/api/contracts.py）

```python
POST /api/contracts/analyze
  - 上传文件 → 触发完整分析流程
  - 返回分析结果 JSON
  - 支持指定合同类型

GET /api/contracts
  - 合同列表（分页、搜索、筛选）

GET /api/contracts/{id}
  - 合同详情 + 分析结果

POST /api/contracts/{id}/feedback
  - 提交用户反馈（对/错）

GET /api/contracts/{id}/report
  - 导出 Markdown 报告
```

### 5.2 知识库 API（server/api/knowledge.py）

```python
GET /api/knowledge/rules
  - 规则列表（分页、按类型筛选）

POST /api/knowledge/rules
  - 新增规则

PUT /api/knowledge/rules/{id}
  - 更新规则

DELETE /api/knowledge/rules/{id}
  - 删除规则

GET /api/knowledge/stats
  - 知识库统计（规则数、置信度分布等）
```

### 5.3 WebSocket 接口（server/api/ws.py）

```
连接: ws://host:port/ws/client?token=xxx

手机端连接后：
- 接收：合同分析进度（逐 step 推送）
- 接收：分析结果（逐条推送）
- 发送：合同文本 + 分析请求
- 发送：用户反馈

管理面板连接后：
- 接收：实时分析状态
- 接收：同步状态更新
```

---

## 六、同步引擎（server/sync/）

### 6.1 WebDAV 同步

```python
class WebDAVSync:
    async def push(self, local_path: str, remote_path: str) -> SyncResult:
        """上传数据库文件到 WebDAV"""

    async def pull(self, remote_path: str, local_path: str) -> SyncResult:
        """从 WebDAV 下载数据库文件"""
```

### 6.2 Git 同步

```python
class GitSync:
    async def commit_and_push(self, message: str) -> SyncResult:
        """git add → commit → push"""

    async def pull(self) -> SyncResult:
        """git pull"""
```

---

## 七、手机端 PWA

### 7.1 核心页面

- **index.html** — 单页应用，通过 JS 切换视图
- **视图**：首页（上传）→ 分析中（进度）→ 结果页 → 历史列表

### 7.2 通信流程

```javascript
// 手机端 Agent Harness（精简版）
class MobileAgent {
    async analyze(file) {
        // 1. 拍照/选文件
        // 2. 发送给电脑端 OCR + 分析（或直连云端 API）
        // 3. 接收流式结果
        // 4. 渲染到页面
    }
}
```

### 7.3 PWA 配置

```json
// manifest.json
{
    "name": "合同红绿灯",
    "short_name": "ClauseLight",
    "start_url": "/",
    "display": "standalone",
    "icons": [...]
}
```

---

## 八、启动与部署

### 8.1 本地启动

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/init_db.py

# 导入基础规则
python scripts/import_rules.py

# 启动服务
python server/main.py
# 或
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

### 8.2 Docker 部署

```yaml
# docker-compose.yml
services:
  clause-light:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
    environment:
      - LLM_DEEPSEEK_API_KEY=${LLM_DEEPSEEK_API_KEY}
```

### 8.3 手机访问

```
同一 WiFi 下：
手机浏览器 → http://电脑IP:8080/mobile/

管理面板：
电脑浏览器 → http://localhost:8080/admin/
```
