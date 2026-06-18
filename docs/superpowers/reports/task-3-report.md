# Task 3: 修复 XSS 安全漏洞 — 实现报告

## 状态: DONE

## 问题分析

通过审查所有前端 JavaScript 文件，发现以下 XSS 漏洞：

### 高危漏洞
1. **合同标题/类型/日期** — contracts.js, contractDetail.js, dashboard.js 中 `c.title`, `c.type`, `c.createdAt` 直接插入 innerHTML
2. **条款内容** — contractDetail.js 中 `clause.clauseNumber`, `clause.clauseTitle`, `clause.riskSummary`, `clause.suggestedClause`, `clause.legalBasis` 全部未转义
3. **批注面板** — contractDetail.js 中 `clause.riskSummary`, `clause.plainExplanation`, `clause.legalBasis`, `clause.suggestedClause` 未转义

### 中危漏洞
4. **搜索输入框反射** — contracts.js 和 knowledge.js 中搜索词直接插入 `value=""` 属性
5. **知识库规则文本** — knowledge.js 中 `r.text`, `r.category`, `law.name` 未转义
6. **toast 通知** — components.js 中消息文本直接插入 innerHTML

### 低危漏洞
7. **设备名称** — settings.js 中 `d.name` 未转义
8. **模型描述** — models.js 中 `m.description` 未转义
9. **同步日志** — sync.js 中 `log.type`, `log.details` 未转义

## 修复方案

### 新增全局 escapeHtml 函数
在 `components.js` 中添加 `escapeHtml(text)` 函数，转义 5 种 HTML 特殊字符：
- `&` → `&amp;`
- `<` → `&lt;`
- `>` → `&gt;`
- `"` → `&quot;`
- `'` → `&#39;`

null/undefined 安全处理：返回空字符串。

### 修改的文件

| 文件 | 修改内容 |
|------|----------|
| `server/static/js/components.js` | 添加 escapeHtml 函数，导出到 Components 模块；修复 toast 消息和 RiskBadge 参数转义 |
| `server/static/js/pages/contracts.js` | 合同标题、类型、模型、日期；搜索输入框 value |
| `server/static/js/pages/contractDetail.js` | 合同标题/类型/日期；条款编号/标题/摘要/建议/依据；批注面板 4 个字段；私有 _escapeHtml 委托全局函数 |
| `server/static/js/pages/dashboard.js` | 合同标题、类型、日期 |
| `server/static/js/pages/knowledge.js` | 规则文本、类别、法规名称；搜索输入框 value；统计页规则文本 |
| `server/static/js/pages/settings.js` | 设备名称 |
| `server/static/js/pages/models.js` | 模型描述 |
| `server/static/js/pages/sync.js` | 同步日志类型和详情 |

## 测试验证

XSS 测试方法：
1. 在合同标题中输入 `<script>alert('xss')</script>`
2. 在搜索框中输入 `"><script>alert(1)</script>`
3. 验证脚本不会执行，内容正确显示为纯文本

## 提交信息

```
fix: 修复 XSS 安全漏洞 — 添加 HTML 转义函数并保护所有用户数据渲染

commit: e75b664e
files: 8 files changed, 47 insertions(+), 38 deletions(-)
```

## 后续建议

1. 考虑使用 Content Security Policy (CSP) 头进一步限制脚本执行
2. 对于 `StatCard` 等组件的 `label`/`value` 参数，建议后续也统一转义
3. 可以在 CI 中添加静态分析工具检测 innerHTML 中的未转义变量
