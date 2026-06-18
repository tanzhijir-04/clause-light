# Task 2: 修复WebSocket错误处理 — 实现报告

**状态:** DONE
**提交:** 583d3a24
**日期:** 2026-06-18

## 问题描述

当Agent分析流水线失败时（如LLM调用失败、数据库写入异常等），服务器只在本地日志中记录错误，但不通过WebSocket发送任何错误消息到手机端。这导致手机端无限等待分析结果，界面永远卡在加载状态。

## 根因分析

`server/api/ws.py` 中的analyze处理块使用了`try/finally`结构（用于清理临时文件），但缺少`except`块来捕获和处理异常。当`agent.analyze()`或数据库操作抛出异常时，异常被外层的WebSocket主循环捕获，仅记录日志后断开连接，手机端收不到任何反馈。

## 修复方案

### 1. 服务器端（server/api/ws.py）

- **空文本校验**：在分析开始前检查`contract_text.strip()`是否为空，若为空则发送`EMPTY_TEXT`错误码并跳过本次处理
- **异常捕获**：将原有的`try/finally`改为`try/except/finally`结构，捕获所有异常
- **错误消息发送**：异常发生时通过`websocket.send_json()`发送`type: "error"`消息，包含错误描述和错误码`ANALYSIS_FAILED`
- **防御性发送**：错误消息的发送本身也包裹在独立的`try/except`中，防止WebSocket已断开时的二次异常
- **临时文件清理**：`finally`块保持不变，确保临时文件始终被清理

### 2. 手机端类型定义（mobile/src/types/api.ts）

- 在`WSMessage`联合类型中新增：`{ type: 'error'; message: string; code?: string }`

### 3. 手机端屏幕（mobile/src/screens/AnalysisScreen.tsx）

- 在WebSocket消息回调中添加`error`类型处理分支
- 收到错误消息时：设置`error`状态（显示红色错误卡片），将`isAnalyzing`设为`false`（停止加载动画）
- 错误UI复用现有的`errorCard`和`errorText`样式

### 4. WebSocket服务层（mobile/src/services/websocket.ts）

- 无需修改。该层通过泛型`MessageHandler`回调传递所有消息，错误消息自然被传递到上层处理

## 错误场景覆盖

| 场景 | 错误码 | 手机端行为 |
|------|--------|-----------|
| 合同文本为空 | `EMPTY_TEXT` | 显示"合同文本不能为空" |
| Agent分析失败 | `ANALYSIS_FAILED` | 显示具体错误信息 |
| 数据库写入失败 | `ANALYSIS_FAILED` | 显示具体错误信息 |
| WebSocket发送失败 | N/A | 静默处理，不崩溃 |

## 验证结果

- 服务器端`ws.py`模块导入成功
- 手机端TypeScript编译通过（零错误）
- 提交并推送到GitHub：583d3a24
