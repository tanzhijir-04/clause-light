# 合同原文标注视图 — 开发提示词

## 任务

实现合同详情页的"原文标注视图"功能：用户打开合同详情后，可切换到原文视图，看到完整合同文本，高风险/中风险条款用荧光笔效果高亮标注，点击高亮段落弹出右侧批注面板显示风险详情。

## 设计原型位置

```
designs/contract-annotated-view/
├── annotated-view.html    # 完整设计原型（React+Babel，仅供参考）
└── data.json              # 原型用的 Mock 数据结构
```

**PRD 文档**：`PRD-annotated-view.md`（根目录）

**注意：原型使用 React+Babel 构建，但实际实现必须使用纯 HTML + CSS + JavaScript（ES6+），不引入任何框架。** 已有的设计令牌、组件、路由模式必须复用。

## 现有代码结构（必须了解）

```
server/static/
├── index.html              # 主入口
├── css/
│   ├── tokens.css          # 设计令牌（CSS 自定义属性，已含风险色变量）
│   ├── base.css            # 重置 + 基础样式
│   ├── layout.css          # 布局（侧边栏 + 主内容区）
│   ├── components.css      # 组件样式
│   └── pages.css           # 页面特定样式（需追加标注视图样式）
├── js/
│   ├── app.js              # 主应用（路由 + 主题 + 初始化）
│   ├── router.js           # Hash 路由器（支持 params）
│   ├── theme.js            # 主题切换
│   ├── api.js              # API 调用封装
│   ├── icons.js            # SVG 图标
│   ├── components.js       # 共享 UI 组件（RiskBadge, RiskDistBar 等）
│   └── pages/
│       ├── contractDetail.js  # 合同详情页（需重写）
│       ├── contracts.js
│       ├── dashboard.js
│       ├── knowledge.js
│       ├── models.js
│       ├── settings.js
│       └── sync.js
```

## 后端改动

### 1. API 返回合同全文

文件：`server/api/contracts.py`

在 `get_contract()` 接口的返回值中增加 `fullText` 字段：

```python
# 在 return 的 dict 中添加：
"fullText": contract.ocr_text or "",
```

### 2. 分析时保存 OCR 原文

文件：`server/api/contracts.py`

在 `analyze_contract()` 接口中，OCR 完成后将原文存入 `contract.ocr_text`：

在 `result = await agent.analyze(...)` 调用之后、保存分析结果之前，添加：

```python
# 保存 OCR 原文到合同记录
if hasattr(result, 'ocr_text') and result.ocr_text:
    contract.ocr_text = result.ocr_text
```

如果 `AnalysisResult` 没有 `ocr_text` 字段，则在 `server/core/agent.py` 的 `ContractAgent.analyze()` 方法中，将 OCR 阶段的全文结果保存到 `AnalysisResult`。

## 前端改动

### 1. 重写合同详情页

文件：`server/static/js/pages/contractDetail.js`

完全重写 `ContractDetailPage`，实现以下功能：

**页面结构**：
- content-header：返回按钮 + 合同标题/副标题 + 风险徽章 + 评分
- 风险分布条：红/黄/绿分段，可点击筛选
- 视图切换 Tab：「条款列表」↔「原文标注」
- content-body：根据当前 Tab 渲染对应视图
- 右侧批注面板（点击高亮条款时弹出）

**Tab 1 — 条款列表视图**（保留现有卡片列表，稍作调整）：
- 每张卡片：条款编号 + 风险徽章 + 标题 + 问题摘要
- 有修改建议的卡片显示建议预览
- 有法律依据的显示法律依据预览
- 点击卡片打开批注面板

**Tab 2 — 原文标注视图**（新增）：
- 渲染完整合同原文（`contract.fullText`）
- 按 `clauseContent` 在原文中定位每条条款的起止位置
- 高风险条款：红色左边框 3px + 红色背景 12% 透明度
- 中风险条款：黄色左边框 3px + 黄色背景 10% 透明度
- 低风险条款：不高亮，保持原文干净
- 高亮区域 hover 时加深背景、显示条款编号
- 点击高亮区域：激活该条款、打开批注面板、滚动到该位置
- 首次进入时自动滚动到第一个红色条款

**批注面板**（AnnoPanel）：
- 宽度 400px，右侧固定
- 顶部：风险徽章 + 条款标题 + 关闭按钮
- 内容区按顺序显示：
  1. 问题摘要（riskSummary）
  2. 通俗解释（plainExplanation）
  3. 法律依据（legalBasis，斜体灰色样式）
  4. 修改建议（suggestedClause，蓝色背景 + 左边框）
  5. 严重度条（10 个色块，根据 severityScore 填充）
- 底部：反馈按钮（标注准确 / 标注不准确），调用 `/api/contracts/{id}/feedback`
- 无内容的区域不渲染

**风险导航**：
- 顶部右侧：「上一条」/「下一条」按钮 + 当前位置计数
- 只在 red + yellow 条款间导航
- 点击时切换批注面板内容并滚动原文到对应位置

**交互逻辑**：
- `activeClauseId` 状态：当前激活的条款 ID
- `currentView` 状态：'list' 或 'annotated'
- `riskFilter` 状态：null 或 'red'/'yellow'/'green'，筛选风险分布条
- 点击高亮段落 → 设置 activeClauseId → 打开批注面板 → 滚动到该位置
- 点击条款卡片 → 同上，但自动切换到原文视图
- 关闭批注面板 → 清除 activeClauseId
- 风险分布条点击 → 筛选高亮显示

**原文标注渲染引擎**（核心函数 `renderAnnotatedText`）：

```javascript
function renderAnnotatedText(fullText, clauses, activeClauseId, onClauseClick) {
  // 1. 按 clauseContent 在 fullText 中定位每条条款
  // 2. 按起始位置排序
  // 3. 未被条款覆盖的文本保持原样
  // 4. 重叠区域取最高风险等级
  // 5. 返回 HTML 字符串，高亮区域用 <span class="clause-mark {riskLevel}" data-clause-id="..."> 包裹
}
```

**定位策略**：
- 优先用 `clauseNumber + clauseTitle` 组合作为搜索锚点（如"第一条\n房屋基本情况"）
- 回退到 `clauseContent` 的前 50 个字符做子串匹配
- 匹配失败时跳过该条款（不崩溃）

### 2. 新增标注视图样式

文件：`server/static/css/pages.css`（在末尾追加）

需要追加的样式：

```css
/* ---- 原文标注视图 ---- */

/* 视图切换 Tab */
.view-tabs { display: flex; border-bottom: 1px solid var(--border-default); }
.view-tab {
  padding: 12px 16px; font-size: 13px; font-weight: 500;
  color: var(--text-secondary); cursor: pointer;
  border-bottom: 2px solid transparent; transition: all .15s;
  user-select: none;
}
.view-tab:hover { color: var(--text-primary); }
.view-tab.active { color: var(--text-primary); border-bottom-color: var(--accent); }

/* 风险分布条（可交互） */
.risk-dist-interactive { display: flex; height: 6px; border-radius: 3px; overflow: hidden; gap: 2px; cursor: pointer; }
.risk-dist-seg { height: 100%; border-radius: 3px; transition: opacity .15s; }
.risk-dist-seg.red { background: var(--risk-red); }
.risk-dist-seg.yellow { background: var(--risk-yellow); }
.risk-dist-seg.green { background: var(--risk-green); }
.risk-dist-seg.dim { opacity: 0.3; }

/* 风险导航按钮 */
.risk-nav { display: flex; align-items: center; gap: 8px; }
.risk-nav-btn {
  display: flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 500;
  border: 1px solid var(--border-default); background: var(--bg-surface);
  color: var(--text-secondary); transition: all .15s;
}
.risk-nav-btn:hover:not(:disabled) { background: var(--bg-surface-hover); color: var(--text-primary); border-color: var(--border-strong); }
.risk-nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.risk-nav-count { font-size: 11px; color: var(--text-tertiary); min-width: 60px; text-align: center; }

/* 原文区域 */
.original-text {
  flex: 1; overflow-y: auto; padding: 24px 32px;
  font-size: 15px; line-height: 1.9; white-space: pre-wrap; scroll-behavior: smooth;
}

/* 条款高亮标记 */
.clause-mark {
  position: relative; cursor: pointer; transition: all .15s;
  border-left: 3px solid transparent; padding-left: 12px;
  margin-left: -3px; border-radius: 0 4px 4px 0;
}
.clause-mark.red { background: rgba(229, 62, 62, 0.12); border-left-color: var(--risk-red); }
.clause-mark.yellow { background: rgba(214, 158, 46, 0.10); border-left-color: var(--risk-yellow); }
.clause-mark:hover { filter: brightness(0.95); }
.clause-mark.active { box-shadow: 0 0 0 2px var(--accent); z-index: 1; position: relative; }
.clause-mark .clause-label {
  position: absolute; top: -10px; right: 8px;
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: var(--radius-full);
  opacity: 0; transition: opacity .15s; pointer-events: none;
}
.clause-mark:hover .clause-label, .clause-mark.active .clause-label { opacity: 1; }
.clause-mark.red .clause-label { background: var(--risk-red); color: #fff; }
.clause-mark.yellow .clause-label { background: var(--risk-yellow); color: #fff; }

/* 批注面板 */
.annotation-panel {
  width: 400px; min-width: 400px; border-left: 1px solid var(--border-default);
  background: var(--bg-surface); display: flex; flex-direction: column;
  overflow: hidden; transition: width .25s ease, min-width .25s ease, opacity .2s ease;
}
.annotation-panel.collapsed { width: 0; min-width: 0; opacity: 0; border-left: none; }
.anno-header {
  padding: 16px 20px; border-bottom: 1px solid var(--border-subtle);
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.anno-close {
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  border-radius: 6px; color: var(--text-tertiary); transition: all .15s;
}
.anno-close:hover { background: var(--bg-surface-hover); color: var(--text-primary); }
.anno-body { flex: 1; overflow-y: auto; padding: 20px; }
.anno-section { margin-bottom: 20px; }
.anno-section-title {
  font-size: 11px; font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;
}
.anno-section-content {
  font-size: 13px; line-height: 1.7; color: var(--text-primary); white-space: pre-wrap;
}
.anno-section-content.legal { color: var(--text-secondary); font-style: italic; }
.anno-section-content.suggest {
  color: var(--accent); background: var(--accent-subtle);
  padding: 12px; border-radius: 6px; border-left: 3px solid var(--accent);
}
.severity-bar { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.severity-blocks { display: flex; gap: 2px; }
.severity-block { width: 16px; height: 8px; border-radius: 2px; background: var(--border-default); }
.severity-text { font-size: 11px; color: var(--text-tertiary); margin-left: 8px; }

/* 响应式 */
@media (max-width: 1024px) {
  .annotation-panel {
    width: 100% !important; min-width: 100% !important;
    position: fixed; bottom: 0; left: 0; right: 0;
    height: 50%; border-left: none;
    border-top: 1px solid var(--border-default);
    border-radius: 8px 8px 0 0; z-index: 10;
    box-shadow: var(--shadow-lg);
  }
  .annotation-panel.collapsed { height: 0; width: 100% !important; min-width: 100% !important; }
  .original-text { padding: 16px; }
}
@media (max-width: 768px) {
  .annotation-panel { height: 60% !important; }
  .original-text { padding: 12px; font-size: 14px; }
}
```

### 3. 更新 components.js

文件：`server/static/js/components.js`

在 `Components` 对象中添加以下组件函数：

```javascript
/** 可交互风险分布条（带点击筛选） */
function RiskDistInteractive(red, yellow, green, filter, onFilter) {
  const total = red + yellow + green;
  if (total === 0) return '';
  return `<div style="display:flex;align-items:center;gap:var(--sp-3)">
    <div class="risk-dist-interactive" style="flex:1">
      ${red > 0 ? `<div class="risk-dist-seg red ${filter && filter !== 'red' ? 'dim' : ''}" style="width:${(red/total)*100}%" data-risk="red"></div>` : ''}
      ${yellow > 0 ? `<div class="risk-dist-seg yellow ${filter && filter !== 'yellow' ? 'dim' : ''}" style="width:${(yellow/total)*100}%" data-risk="yellow"></div>` : ''}
      ${green > 0 ? `<div class="risk-dist-seg green ${filter && filter !== 'green' ? 'dim' : ''}" style="width:${(green/total)*100}%" data-risk="green"></div>` : ''}
    </div>
    <div style="display:flex;gap:12px;font-size:11px;color:var(--text-secondary);white-space:nowrap">
      <span style="color:var(--risk-red);font-weight:${filter==='red'?700:400};cursor:pointer" data-risk="red">红 ${red}</span>
      <span style="color:var(--risk-yellow);font-weight:${filter==='yellow'?700:400};cursor:pointer" data-risk="yellow">黄 ${yellow}</span>
      <span style="color:var(--risk-green);font-weight:${filter==='green'?700:400};cursor:pointer" data-risk="green">绿 ${green}</span>
    </div>
  </div>`;
}

/** 严重度条 */
function SeverityBar(score, maxScore = 10) {
  const color = score >= 7 ? 'var(--risk-red)' : score >= 4 ? 'var(--risk-yellow)' : 'var(--risk-green)';
  let blocks = '';
  for (let i = 0; i < maxScore; i++) {
    blocks += `<div class="severity-block" style="${i < score ? 'background:' + color : ''}"></div>`;
  }
  return `<div class="severity-bar">
    <div class="severity-blocks">${blocks}</div>
    <span class="severity-text">${score}/${maxScore}</span>
  </div>`;
}
```

### 4. 更新 api.js

文件：`server/static/js/api.js`

确认 `API.contracts.get(id)` 返回的数据包含 `fullText` 字段（后端已改，前端无需额外改动，但需确认 `contract.fullText` 可用）。

如果 `API.contracts.get()` 有自定义的数据转换逻辑，确保 `fullText` 被保留。

## 实现要点

### 原文标注渲染算法

这是整个功能的核心，必须仔细实现：

```
输入：fullText（完整合同文本），clauses（条款数组）
输出：HTML 字符串，高亮区域被 <span> 包裹

算法：
1. 对每条 clause，用 clauseNumber + "\n" + clauseTitle 在 fullText 中搜索
2. 如果找到，记录 {start, end, clause}，end = start + clauseContent.length
3. 如果找不到，尝试用 clauseContent 的前 30 个字符搜索
4. 按 start 排序
5. 遍历 segs，生成 HTML：
   - segs 之间的普通文本：直接输出
   - segs 覆盖的文本：用 <span class="clause-mark {riskLevel}" data-clause-id="..."> 包裹
6. 如果两个 seg 重叠，取风险等级更高的那个
```

### 响应式适配

- 桌面（>1024px）：原文 + 右侧批注面板并排
- 平板/手机（<=1024px）：批注面板变为底部抽屉，固定定位，高度 50-60%
- 侧边栏在详情页隐藏（已有逻辑）

### 错误处理

- `fullText` 为空时：显示"暂无合同原文"提示
- 条款定位失败时：跳过该条款，不高亮
- 批注面板内容为空时：不渲染对应区块
- API 请求失败时：显示错误提示

## 验收标准

- [ ] 合同详情页顶部有「条款列表」和「原文标注」两个 Tab
- [ ] 条款列表 Tab 功能与原有详情页一致
- [ ] 原文标注 Tab 显示完整合同原文
- [ ] 高风险条款有红色左边框 + 红色背景高亮
- [ ] 中风险条款有黄色左边框 + 黄色背景高亮
- [ ] 低风险条款不高亮
- [ ] 点击高亮段落弹出右侧批注面板
- [ ] 批注面板显示：问题摘要、通俗解释、法律依据、修改建议、严重度
- [ ] 上一条/下一条风险导航按钮可用
- [ ] 风险分布条可点击筛选
- [ ] 首次进入自动滚动到第一个红色条款
- [ ] 暗色主题下高亮颜色正确
- [ ] 手机端批注面板变为底部抽屉
- [ ] 无外部 CDN 依赖
- [ ] 所有文本为中文
