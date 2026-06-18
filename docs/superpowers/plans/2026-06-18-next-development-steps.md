# ClauseLight 下一步开发实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复现有关键bug并完善核心功能，提升产品质量和用户体验

**Architecture:** 采用分阶段修复策略，优先处理影响用户体验的bug，然后完善测试覆盖，最后实现缺失的核心功能

**Tech Stack:** Python/FastAPI, React Native/Expo, SQLAlchemy, PaddleOCR, WebSocket, pytest

## Global Constraints

- Python >= 3.10
- React Native (Expo SDK 52)
- SQLite 数据库
- 所有代码改动后立即提交并推送到 GitHub
- commit message 使用中文
- 代码注释使用中文
- 所有 API 返回 JSON 格式

---

## 第一阶段：修复关键用户体验Bug（预计2天）

### Task 1: 修复搜索输入框失焦问题

**Files:**
- Modify: `server/static/js/pages/contracts.js:1-50`
- Modify: `server/static/js/pages/knowledge.js:1-50`
- Modify: `server/static/js/app.js:100-150`

**Interfaces:**
- Consumes: 现有的页面渲染逻辑
- Produces: 修复后的搜索功能，不再失焦

- [ ] **Step 1: 分析当前实现**

读取相关文件，理解当前的搜索实现：
```bash
grep -n "renderCurrentPage\|searchInput" server/static/js/pages/contracts.js
grep -n "renderCurrentPage\|searchInput" server/static/js/pages/knowledge.js
```

- [ ] **Step 2: 修改 contracts.js 搜索逻辑**

在 `contracts.js` 中实现防抖搜索：
```javascript
// 添加防抖变量
let searchDebounce = null;

// 修改搜索输入处理
function handleSearch(value) {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    // 执行实际搜索
    performSearch(value);
  }, 300);
}

// 保留输入框焦点
function performSearch(value) {
  const input = document.querySelector('.search-input');
  const currentValue = input ? input.value : value;
  // 执行搜索逻辑
  renderContractsList(filteredContracts);
  // 恢复焦点
  if (input) {
    input.focus();
    input.setSelectionRange(currentValue.length, currentValue.length);
  }
}
```

- [ ] **Step 3: 修改 knowledge.js 搜索逻辑**

同样的防抖模式应用到知识库页面：
```javascript
let knowledgeSearchDebounce = null;

function handleKnowledgeSearch(value) {
  clearTimeout(knowledgeSearchDebounce);
  knowledgeSearchDebounce = setTimeout(() => {
    performKnowledgeSearch(value);
  }, 300);
}
```

- [ ] **Step 4: 测试修复效果**

启动服务器，手动测试：
1. 在合同页面搜索框中输入文字
2. 验证输入框不再失焦
3. 验证搜索功能正常工作
4. 在知识库页面重复测试

- [ ] **Step 5: 提交修复**

```bash
git add server/static/js/pages/contracts.js server/static/js/pages/knowledge.js
git commit -m "fix: 修复搜索输入框失焦问题

问题描述：
- 合同页面和知识库页面的搜索输入框在每次按键时都会失焦
- 原因是 renderCurrentPage() 重新渲染整个页面HTML

修复方案：
- 实现防抖搜索（300ms延迟）
- 保留输入框焦点和光标位置
- 避免不必要的页面重渲染"
```

---

### Task 2: 修复WebSocket错误处理

**Files:**
- Modify: `server/api/ws.py:85-100`
- Modify: `mobile/src/services/websocket.ts:50-80`

**Interfaces:**
- Consumes: 现有的WebSocket消息格式
- Produces: 错误消息发送到手机端

- [ ] **Step 1: 修改服务器端错误处理**

在 `server/api/ws.py` 的 analyze 处理器中添加错误消息发送：
```python
try:
    # 执行 Agent 分析
    agent = ContractAgent()
    result = await agent.analyze(...)
    # ... 保存到数据库 ...
except Exception as e:
    # 发送错误消息到手机端
    await websocket.send_json({
        "type": "error",
        "message": f"分析失败: {str(e)}",
        "code": "ANALYSIS_FAILED"
    })
    logger.error("分析失败: %s", e)
```

- [ ] **Step 2: 修改手机端错误处理**

在 `mobile/src/services/websocket.ts` 中处理错误消息：
```typescript
// 在消息处理中添加错误类型
case 'error':
  // 处理错误消息
  this.onError?.(new Error(message.message));
  break;
```

- [ ] **Step 3: 在 AnalysisScreen 中显示错误**

修改 `mobile/src/screens/AnalysisScreen.tsx` 显示WebSocket错误：
```typescript
// 在状态中添加 error 类型
const [error, setError] = useState<string | null>(null);

// 在WebSocket回调中处理错误
ws.connect(
  (msg: WSMessage) => {
    if (msg.type === 'error') {
      setError(msg.message);
      setIsAnalyzing(false);
    }
    // ... 其他处理 ...
  },
  // ...
);
```

- [ ] **Step 4: 测试错误场景**

1. 模拟Agent分析失败（如无效输入）
2. 验证手机端显示错误消息
3. 验证不会无限等待

- [ ] **Step 5: 提交修复**

```bash
git add server/api/ws.py mobile/src/services/websocket.ts mobile/src/screens/AnalysisScreen.tsx
git commit -m "fix: 修复WebSocket错误处理问题

问题描述：
- Agent分析失败时，手机端会无限等待响应
- 服务器只记录日志，不发送错误消息

修复方案：
- 服务器发送错误消息到手机端
- 手机端处理错误消息并显示
- 添加错误状态管理"
```

---

### Task 3: 修复XSS安全漏洞

**Files:**
- Modify: `server/static/js/components.js:1-30`
- Modify: `server/static/js/pages/contracts.js:100-150`

**Interfaces:**
- Consumes: 用户输入数据
- Produces: 安全的HTML输出

- [ ] **Step 1: 创建通用转义函数**

在 `components.js` 中添加XSS防护函数：
```javascript
// XSS防护函数
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 安全的HTML插入
function safeHtml(element, html) {
  element.innerHTML = escapeHtml(html);
}
```

- [ ] **Step 2: 修改合同页面渲染**

在 `contracts.js` 中使用安全渲染：
```javascript
// 修改合同标题渲染
function renderContractTitle(contract) {
  return `<h3 class="contract-title">${escapeHtml(contract.title)}</h3>`;
}

// 修改合同类型渲染
function renderContractType(contract) {
  return `<span class="contract-type">${escapeHtml(contract.type)}</span>`;
}
```

- [ ] **Step 3: 测试XSS防护**

1. 在合同标题中输入 `<script>alert('xss')</script>`
2. 验证脚本不会执行
3. 验证内容正确显示

- [ ] **Step 4: 提交修复**

```bash
git add server/static/js/components.js server/static/js/pages/contracts.js
git commit -m "fix: 修复XSS安全漏洞

问题描述：
- 用户输入的数据直接插入HTML，存在XSS攻击风险
- 合同标题、类型等字段未转义

修复方案：
- 添加通用的escapeHtml函数
- 在所有用户数据渲染处使用转义
- 防止恶意脚本执行"
```

---

## 第二阶段：完善测试覆盖（预计2天）

### Task 4: 添加WebSocket测试

**Files:**
- Create: `tests/test_api_ws.py`
- Modify: `tests/conftest.py:50-80`

**Interfaces:**
- Consumes: FastAPI测试客户端
- Produces: WebSocket测试用例

- [ ] **Step 1: 创建WebSocket测试文件**

创建 `tests/test_api_ws.py`：
```python
"""WebSocket 接口测试"""

import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

class TestWebSocketConnection:
    """测试WebSocket连接"""

    def test_connect_success(self):
        """测试成功连接"""
        with client.websocket_connect("/ws/client") as ws:
            # 发送ping消息
            ws.send_json({"type": "ping"})
            # 接收pong响应
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_connect_multiple_clients(self):
        """测试多客户端连接"""
        # 需要实现多客户端测试
        pass

class TestWebSocketAnalyze:
    """测试WebSocket分析功能"""

    def test_analyze_empty_text(self):
        """测试空文本分析"""
        with client.websocket_connect("/ws/client") as ws:
            ws.send_json({
                "type": "analyze",
                "text": "",
                "contractType": ""
            })
            # 应该收到错误消息
            data = ws.receive_json()
            assert data["type"] == "error"

    def test_analyze_with_mock_agent(self):
        """测试分析功能（模拟Agent）"""
        # 需要mock ContractAgent
        pass

class TestWebSocketDisconnect:
    """测试WebSocket断开连接"""

    def test_disconnect_cleanup(self):
        """测试断开连接后清理"""
        with client.websocket_connect("/ws/client") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()
        # 连接断开后应该清理资源
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /c/Users/20300/Desktop/clause-light
python -m pytest tests/test_api_ws.py -v
```

预期：测试失败，因为需要mock依赖

- [ ] **Step 3: 添加必要的mock**

在 `tests/conftest.py` 中添加WebSocket测试fixture：
```python
@pytest.fixture
def mock_agent():
    """模拟ContractAgent"""
    with patch('server.api.ws.ContractAgent') as mock:
        agent_instance = mock.return_value
        agent_instance.analyze.return_value = MockAnalysisResult()
        yield agent_instance
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_api_ws.py -v
```

预期：所有测试通过

- [ ] **Step 5: 提交测试**

```bash
git add tests/test_api_ws.py tests/conftest.py
git commit -m "test: 添加WebSocket接口测试

测试覆盖：
- WebSocket连接测试
- ping/pong心跳测试
- 分析请求测试
- 断开连接清理测试

使用mock模拟Agent依赖，确保测试独立性"
```

---

### Task 5: 添加OCR功能测试

**Files:**
- Create: `tests/test_ocr.py`
- Modify: `requirements.txt:10-15`

**Interfaces:**
- Consumes: PaddleOCR模拟
- Produces: OCR测试用例

- [ ] **Step 1: 创建OCR测试文件**

创建 `tests/test_ocr.py`：
```python
"""OCR 功能测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from server.core.ocr import OCREngine

class TestOCREngine:
    """测试OCR引擎"""

    @patch('server.core.ocr.PaddleOCR')
    def test_recognize_image(self, mock_paddle):
        """测试图片文字识别"""
        # 模拟PaddleOCR返回
        mock_instance = mock_paddle.return_value
        mock_instance.ocr.return_value = [
            [[(10, 10), (100, 10), (100, 50), (10, 50)],
             ('测试文本', 0.95)]
        ]

        engine = OCREngine()
        result = engine.recognize('test.jpg')

        assert len(result) == 1
        assert result[0]['text'] == '测试文本'
        assert result[0]['confidence'] == 0.95

    @patch('server.core.ocr.PaddleOCR')
    def test_recognize_empty_image(self, mock_paddle):
        """测试空白图片识别"""
        mock_instance = mock_paddle.return_value
        mock_instance.ocr.return_value = []

        engine = OCREngine()
        result = engine.recognize('empty.jpg')

        assert len(result) == 0

    @patch('server.core.ocr.PaddleOCR')
    def test_recognize_with_error(self, mock_paddle):
        """测试识别错误处理"""
        mock_instance = mock_paddle.return_value
        mock_instance.ocr.side_effect = Exception("识别失败")

        engine = OCREngine()
        with pytest.raises(Exception):
            engine.recognize('error.jpg')
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_ocr.py -v
```

预期：测试失败，因为需要安装pytest-cov

- [ ] **Step 3: 更新依赖**

在 `requirements.txt` 中添加：
```
pytest-cov>=4.1.0
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pip install pytest-cov
python -m pytest tests/test_ocr.py -v
```

预期：所有测试通过

- [ ] **Step 5: 提交测试**

```bash
git add tests/test_ocr.py requirements.txt
git commit -m "test: 添加OCR功能测试

测试覆盖：
- 图片文字识别测试
- 空白图片处理测试
- 错误处理测试

使用mock模拟PaddleOCR，避免依赖真实OCR模型"
```

---

### Task 6: 添加Connection API测试

**Files:**
- Create: `tests/test_api_connection.py`

**Interfaces:**
- Consumes: FastAPI测试客户端
- Produces: Connection API测试用例

- [ ] **Step 1: 创建Connection API测试文件**

创建 `tests/test_api_connection.py`：
```python
"""Connection API 接口测试"""

import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

class TestConnectionInfo:
    """测试连接信息接口"""

    def test_get_connection_info(self):
        """测试获取连接信息"""
        response = client.get("/api/connection/info")
        assert response.status_code == 200
        data = response.json()
        assert "host" in data
        assert "port" in data
        assert "ws_url" in data
        assert "http_url" in data

class TestConnectionHealth:
    """测试健康检查接口"""

    def test_health_check(self):
        """测试健康检查"""
        response = client.get("/api/connection/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "uptime" in data
        assert "active_connections" in data

class TestConnectionDevices:
    """测试设备列表接口"""

    def test_get_devices_empty(self):
        """测试获取空设备列表"""
        response = client.get("/api/connection/devices")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total" in data
        assert "online" in data
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_api_connection.py -v
```

预期：所有测试通过

- [ ] **Step 3: 提交测试**

```bash
git add tests/test_api_connection.py
git commit -m "test: 添加Connection API测试

测试覆盖：
- 连接信息接口测试
- 健康检查接口测试
- 设备列表接口测试
"
```

---

## 第三阶段：完善核心功能（预计3天）

### Task 7: 实现合同删除功能

**Files:**
- Modify: `server/api/contracts.py:50-80`
- Modify: `server/static/js/pages/contracts.js:200-250`

**Interfaces:**
- Consumes: 现有的数据库模型
- Produces: 删除合同API

- [ ] **Step 1: 添加删除合同API**

在 `server/api/contracts.py` 中添加：
```python
@router.delete("/contracts/{contract_id}")
async def delete_contract(contract_id: str):
    """删除合同及其分析结果"""
    async with async_session_factory() as db:
        # 删除条款分析
        await db.execute(
            delete(ClauseAnalysis).where(
                ClauseAnalysis.analysis_id == contract_id
            )
        )

        # 删除分析记录
        await db.execute(
            delete(Analysis).where(Analysis.contract_id == contract_id)
        )

        # 删除合同
        await db.execute(
            delete(Contract).where(Contract.id == contract_id)
        )

        await db.commit()

    return {"success": True, "message": "合同已删除"}
```

- [ ] **Step 2: 添加前端删除按钮**

在 `contracts.js` 中添加删除功能：
```javascript
function renderDeleteButton(contract) {
  return `
    <button class="delete-btn" onclick="deleteContract('${contract.id}')">
      <i class="fas fa-trash"></i>
    </button>
  `;
}

async function deleteContract(contractId) {
  if (confirm('确定要删除这个合同吗？')) {
    try {
      await fetch(`/api/contracts/${contractId}`, { method: 'DELETE' });
      // 刷新列表
      loadContracts();
    } catch (error) {
      alert('删除失败');
    }
  }
}
```

- [ ] **Step 3: 测试删除功能**

1. 创建测试合同
2. 点击删除按钮
3. 确认删除
4. 验证合同已删除

- [ ] **Step 4: 提交功能**

```bash
git add server/api/contracts.py server/static/js/pages/contracts.js
git commit -m "feat: 实现合同删除功能

功能描述：
- 添加DELETE /api/contracts/{id}接口
- 删除合同时同时删除关联的分析和条款
- 前端添加删除按钮和确认对话框

数据库操作：
- 删除ClauseAnalysis记录
- 删除Analysis记录
- 删除Contract记录"
```

---

### Task 8: 实现反馈到知识库管道

**Files:**
- Modify: `server/api/contracts.py:100-120`
- Modify: `server/core/knowledge.py:200-250`

**Interfaces:**
- Consumes: 现有的知识库引擎
- Produces: 自动学习功能

- [ ] **Step 1: 修改反馈处理逻辑**

在 `server/api/contracts.py` 中修改：
```python
@router.post("/contracts/{contract_id}/feedback")
async def submit_feedback(
    contract_id: str,
    clause_analysis_id: str = Form(...),
    feedback: str = Form(...),
):
    """提交条款反馈并触发自动学习"""
    async with async_session_factory() as db:
        # 更新条款分析的反馈
        clause = await db.get(ClauseAnalysis, clause_analysis_id)
        if clause:
            clause.user_feedback = feedback
            await db.commit()

            # 如果反馈是"不正确"，触发自动学习
            if feedback == "incorrect":
                await trigger_auto_learning(clause)

    return {"success": True}
```

- [ ] **Step 2: 实现自动学习函数**

在 `server/core/knowledge.py` 中添加：
```python
async def trigger_auto_learning(clause: ClauseAnalysis):
    """触发自动学习流程"""
    from server.core.knowledge import KnowledgeEngine

    engine = KnowledgeEngine()

    # 创建新的知识规则
    new_rule = {
        "text": clause.clause_content,
        "category": clause.risk_type or "通用",
        "confidence": 0.6,  # 初始置信度较低
        "source": "auto_learn",
        "usage_count": 1,
    }

    # 添加到知识库
    await engine.add_rule(new_rule)

    logger.info("自动学习：从反馈中创建新规则 %s", clause.id)
```

- [ ] **Step 3: 测试自动学习**

1. 提交一个"不正确"的反馈
2. 检查知识库是否添加了新规则
3. 验证规则内容正确

- [ ] **Step 4: 提交功能**

```bash
git add server/api/contracts.py server/core/knowledge.py
git commit -m "feat: 实现反馈到知识库自动学习管道

功能描述：
- 用户提交"不正确"反馈时触发自动学习
- 从条款内容创建新的知识规则
- 初始置信度设置为0.6

流程：
1. 用户提交反馈
2. 更新条款分析记录
3. 如果是"不正确"，创建新规则
4. 规则进入待审核队列"
```

---

### Task 9: 添加基本认证中间件

**Files:**
- Create: `server/core/auth.py`
- Modify: `server/main.py:50-80`

**Interfaces:**
- Consumes: API密钥配置
- Produces: 认证中间件

- [ ] **Step 1: 创建认证模块**

创建 `server/core/auth.py`：
```python
"""认证中间件"""

from fastapi import Request, HTTPException
from fastapi.security import APIKeyHeader
from server.config import settings

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(request: Request):
    """验证API密钥"""
    # 跳过健康检查和静态文件
    if request.url.path in ["/", "/health", "/api/connection/health"]:
        return

    # 跳过静态文件
    if request.url.path.startswith("/static"):
        return

    # 验证API密钥
    api_key = request.headers.get("X-API-Key")
    if settings.API_KEY and api_key != settings.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="无效的API密钥"
        )
```

- [ ] **Step 2: 在main.py中添加中间件**

修改 `server/main.py`：
```python
from server.core.auth import verify_api_key

app = FastAPI(...)

# 添加认证中间件
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    await verify_api_key(request)
    response = await call_next(request)
    return response
```

- [ ] **Step 3: 在config.py中添加配置**

在 `server/config.py` 中添加：
```python
API_KEY: str = ""  # 空字符串表示禁用认证
```

- [ ] **Step 4: 测试认证功能**

1. 设置API密钥
2. 不带密钥访问API，验证返回401
3. 带正确密钥访问，验证正常
4. 访问健康检查，验证无需密钥

- [ ] **Step 5: 提交功能**

```bash
git add server/core/auth.py server/main.py server/config.py
git commit -m "feat: 添加基本认证中间件

功能描述：
- 添加API密钥认证
- 跳过健康检查和静态文件
- 可通过环境变量配置

安全改进：
- 防止未授权访问API
- 保护LLM配置等敏感接口
- 支持后续扩展为更复杂的认证"
```

---

## 第四阶段：改进基础设施（预计1天）

### Task 10: 添加测试覆盖率报告

**Files:**
- Modify: `pytest.ini:1-10`
- Modify: `requirements.txt:10-15`

**Interfaces:**
- Consumes: pytest配置
- Produces: 测试覆盖率报告

- [ ] **Step 1: 更新pytest配置**

修改 `pytest.ini`：
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
addopts = --cov=server --cov-report=term-missing --cov-report=html
```

- [ ] **Step 2: 更新依赖**

在 `requirements.txt` 中添加：
```
pytest-cov>=4.1.0
```

- [ ] **Step 3: 运行测试生成覆盖率报告**

```bash
python -m pytest --cov=server --cov-report=html
```

- [ ] **Step 4: 提交配置**

```bash
git add pytest.ini requirements.txt
git commit -m "chore: 添加测试覆盖率报告配置

配置：
- 使用pytest-cov生成覆盖率报告
- 添加终端和HTML报告
- 配置覆盖率目标目录"
```

---

## 执行说明

**推荐执行顺序：**
1. 第一阶段：修复关键用户体验Bug（Task 1-3）
2. 第二阶段：完善测试覆盖（Task 4-6）
3. 第三阶段：完善核心功能（Task 7-9）
4. 第四阶段：改进基础设施（Task 10）

**每个Task完成后：**
- 运行相关测试验证
- 手动测试功能
- 提交代码
- 推送到GitHub

**预计总时间：** 8天

**风险评估：**
- 低风险：所有修改都是向后兼容的
- 测试覆盖：每个Task都有测试验证
- 回归风险：分阶段执行，每阶段完成后验证
