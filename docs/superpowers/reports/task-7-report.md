# Task 7 Report: 实现合同删除功能

## Status: DONE

## 实现内容

### 后端: DELETE API (`server/api/contracts.py`)

添加了 `DELETE /api/contracts/{contract_id}` 端点，实现级联删除:

1. 验证合同是否存在（不存在返回 404）
2. 查询该合同的所有 Analysis ID
3. 删除所有关联的 ClauseAnalysis 记录（通过 analysis_id.in_）
4. 删除所有关联的 Analysis 记录（通过 contract_id）
5. 删除 Contract 记录本身
6. 清理上传的源文件（source_file，如果存在且可删除）
7. 提交事务

返回格式: `{"success": true, "message": "合同已删除"}`

### 前端 API (`server/static/js/api.js`)

在 `API.contracts` 对象中添加了 `delete(id)` 方法，发送 `DELETE /api/contracts/{id}` 请求。支持 mock 模式。

### 合同列表页 (`server/static/js/pages/contracts.js`)

- 表格新增「操作」列（固定宽度 60px）
- 每行添加红色垃圾桶删除按钮 (`btn-danger btn-sm btn-icon`)
- 使用 `event.stopPropagation()` 阻止行点击事件冒泡
- 添加 `deleteContract(contractId, contractTitle)` 异步方法:
  - 弹出确认对话框，显示合同名称
  - 调用 `API.contracts.delete()` 执行删除
  - 成功后显示 toast 提示并刷新列表（保持搜索/筛选状态）
  - 失败后显示错误 toast

### 合同详情页 (`server/static/js/pages/contractDetail.js`)

- 头部右侧添加「删除」按钮（`btn-danger btn-sm`，带垃圾桶图标）
- 添加 `_deleteContract()` 异步方法:
  - 弹出确认对话框，显示合同名称
  - 调用 `API.contracts.delete()` 执行删除
  - 成功后显示 toast 并导航回合同列表页
  - 失败后显示错误 toast

## 修改文件

| 文件 | 改动 |
|------|------|
| `server/api/contracts.py` | 添加 `delete` 导入，新增 `delete_contract` 端点 (+47 行) |
| `server/static/js/api.js` | 添加 `contracts.delete()` 方法 (+4 行) |
| `server/static/js/pages/contracts.js` | 添加操作列、删除按钮、`deleteContract` 函数 (+28 行) |
| `server/static/js/pages/contractDetail.js` | 添加删除按钮、`_deleteContract` 函数 (+18 行) |

## 测试结果

- 合同相关测试全部通过: 25 passed, 151 deselected
- 无新增测试失败

## Git 提交

- Commit: `26ccb4f6` feat: 实现合同删除功能
- 已推送到 GitHub main 分支
