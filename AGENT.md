# AGENT.md — Agent 行为规范与开发边界

## Agent 角色

你是 ClauseLight 项目的开发 Agent。你的任务是按照 CLAUDE.md 和 TECHNICAL.md 的规范，
实现合同风险审查工具的各个模块。

## 核心约束（必须遵守）

### 1. 技术栈边界
- **后端只能用**：Python、FastAPI、SQLAlchemy、SQLite、PaddleOCR、sentence-transformers、openai SDK、webdavclient3、boto3
- **前端只能用**：纯 HTML、CSS、JavaScript（ES6+），不能引入 React/Vue/Angular 等框架
- **不能用**：PostgreSQL、MongoDB、Redis、Docker（除最终部署外）、TypeScript
- **新增依赖**前必须先说明理由，获得确认后才能添加

### 2. 架构边界
- **不能修改数据库表结构**除非明确要求
- **不能修改已有 API 接口的签名**除非明确要求
- **不能删除已有功能代码**只能新增或修改
- **不能引入新的外部服务**（如新的云 API）除非明确要求
- **不能修改 CLAUDE.md 和 AGENT.md**

### 3. 代码规范边界
- **必须使用 type hints**
- **必须处理异常**，不能有裸 except
- **LLM 调用必须通过 `server/core/llm.py`**，不能直接调用 openai SDK
- **Prompt 模板必须存放在 `server/core/prompts/`**，不能硬编码在业务逻辑中
- **数据库操作必须通过 SQLAlchemy ORM**，不能写裸 SQL
- **前端代码必须支持离线运行**（无外部 CDN 依赖）

### 4. 安全边界
- **API Key 不能硬编码**，必须从环境变量或配置文件读取
- **不能在日志中打印完整的合同内容或 API Key**
- **文件上传必须校验类型**（只允许图片和 PDF）
- **用户输入必须做基本校验**（防注入、防 XSS）

## 开发流程规范

### 每次开发一个模块时：

1. **先读**：读取 TECHNICAL.md 了解该模块的技术要求
2. **再写**：按照技术方案实现代码
3. **自检**：
   - 代码是否使用了 type hints？
   - 异常是否处理了？
   - 是否通过了 llm.py 网关？
   - prompt 是否在 prompts/ 目录？
   - 数据库操作是否用了 ORM？
4. **测试**：编写简单的单元测试或集成测试
5. **提交**：git commit，commit message 使用中文

### 不允许做的事情：

- ❌ 跳过异常处理
- ❌ 在代码中硬编码 API Key、密码
- ❌ 直接调用 openai SDK（必须通过 llm.py）
- ❌ 在前端使用外部 CDN
- ❌ 使用 print() 做日志（必须用 logging 模块）
- ❌ 在没有读取 TECHNICAL.md 的情况下开始编码
- ❌ 一次性实现多个模块（每次只做一个模块）
- ❌ 修改其他模块的代码（除非当前任务明确要求）

### 允许做的事情：

- ✅ 新增 Python 文件
- ✅ 新增前端页面
- ✅ 新增 API 接口（不修改已有接口）
- ✅ 新增数据库表（通过 migration）
- ✅ 新增依赖（需先说明理由）
- ✅ 编写测试
- ✅ 编写文档
- ✅ 重构当前模块内部代码（不改变外部接口）

## 模块开发顺序

按 P0 范围，严格按以下顺序开发：

```
Phase 1: 基础设施
  1.1 项目配置（config.py, database.py）
  1.2 LLM 网关（llm.py）
  1.3 Prompt 模板框架

Phase 2: 核心引擎
  2.1 OCR 封装（ocr.py）
  2.2 Agent Harness（agent.py）
  2.3 知识库引擎（knowledge.py）

Phase 3: API 层
  3.1 合同分析 API（contracts.py）
  3.2 WebSocket 接口（ws.py）
  3.3 FastAPI 主入口（main.py）

Phase 4: 前端
  4.1 电脑端管理面板
  4.2 手机端 PWA

Phase 5: 知识库数据
  5.1 基础规则库（50+ 条）
  5.2 法规库
```

每个 Phase 完成后需要：
- 确认该 Phase 的代码可以独立运行
- 确认没有破坏已有功能
- 提交 git commit

## 错误处理要求

```python
# 正确的错误处理方式
try:
    result = await llm_client.chat(prompt)
except LLMRateLimitError:
    logger.warning("LLM 限流，等待重试")
    await asyncio.sleep(2)
    result = await llm_client.chat(prompt)
except LLMConnectionError as e:
    logger.error(f"LLM 连接失败: {e}")
    return FallbackResult(
        status="degraded",
        message="LLM 服务不可用，使用规则引擎兜底"
    )
```

```python
# 错误的方式
try:
    result = await llm_client.chat(prompt)
except:  # ❌ 裸 except
    pass  # ❌ 吞掉异常
```

## 日志规范

```python
import logging

logger = logging.getLogger(__name__)

# 使用不同级别
logger.debug("OCR 识别完成，共 %d 个文本块", len(blocks))
logger.info("合同分析开始: contract_id=%s", contract_id)
logger.warning("LLM 输出格式异常，触发修复: %s", raw_output[:100])
logger.error("OCR 识别失败: %s", str(e))
```

## 提交规范

```
feat: 新增合同分析 API
fix: 修复 OCR 多页拼接问题
docs: 更新 TECHNICAL.md
refactor: 重构 LLM 网关路由逻辑
test: 添加 Agent Harness 单元测试
chore: 更新 requirements.txt
```
