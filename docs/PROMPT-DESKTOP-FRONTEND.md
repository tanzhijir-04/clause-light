# ClauseLight 桌面端前端开发提示词

## 任务

请根据已完成的 UI 设计原型，实现 ClauseLight 电脑端管理面板的前端代码。

## 设计原型位置

```
designs/clause-light-desktop/
├── index.html          # 原型入口（React+Babel，仅供设计参考）
├── styles.css          # 设计系统 CSS（需要参考，但需重构为纯 CSS）
├── data.jsx            # Mock 数据结构（参考数据格式）
├── icons.jsx           # 图标定义（参考图标形状）
├── components.jsx      # 组件定义（参考组件结构）
├── _page_*.jsx         # 5 个页面的组件定义
└── app.jsx             # 路由逻辑
```

**注意：原型使用 React+Babel 构建，但实际实现必须使用纯 HTML + CSS + JavaScript（ES6+），不引入任何框架。**

## 设计方向

使用 **V1 Notion 风格**，设计令牌见原型 `styles.css` 中 `[data-variant="v1"]` 的变量定义。需要同时支持 **亮色主题和暗色主题**（默认亮色），通过 CSS 自定义属性 + `data-theme` 属性切换。

## 技术约束（必须遵守）

- 纯 HTML + CSS + JavaScript（ES6+），无框架依赖
- 无外部 CDN 依赖（PWA 离线可用）
- 所有前端代码放在 `server/static/` 目录下
- 图标使用内联 SVG，不依赖图标库
- 字体使用系统字体栈（-apple-system, PingFang SC, Noto Sans SC 等）
- CSS 使用自定义属性实现主题切换
- 所有文本使用中文

## 目录结构

```
server/static/
├── index.html          # 主入口（SPA）
├── css/
│   ├── tokens.css      # 设计令牌（CSS 自定义属性）
│   ├── base.css        # 重置 + 基础样式
│   ├── layout.css      # 布局（侧边栏 + 主内容区）
│   ├── components.css  # 组件样式（卡片、按钮、表格、表单等）
│   └── pages.css       # 页面特定样式
├── js/
│   ├── app.js          # 主应用（路由 + 主题切换 + 初始化）
│   ├── router.js       # 简易路由（hash 或 history）
│   ├── theme.js        # 主题切换逻辑（亮/暗）
│   ├── api.js          # API 调用封装（与后端通信）
│   ├── icons.js        # SVG 图标函数
│   ├── components.js   # 共享 UI 组件（渲染函数）
│   └── pages/
│       ├── dashboard.js    # 仪表盘
│       ├── contracts.js    # 合同管理
│       ├── knowledge.js    # 知识库管理
│       ├── sync.js         # 同步管理
│       └── settings.js     # 设置
└── manifest.json       # PWA manifest（可选）
```

## 页面功能规格

### 1. 仪表盘（dashboard）

**布局：**
- 顶部：4 列统计卡片（合同总数、平均风险分、知识库规则数、连接设备数）
- 中部左侧（2/3 宽）：最近分析表格（合同名、类型、评分、风险分布条、日期）
- 中部右侧上（1/3 宽）：风险分布统计（红/黄/绿数量 + 分布条）
- 中部右侧下：快速上传区域（拖放 + 点击上传）

**交互：**
- 统计卡片带图标，hover 时轻微上浮
- 表格行可点击，跳转到合同详情
- 上传区域支持拖放高亮
- 数据从 `/api/contracts` 和 `/api/knowledge/stats` 获取

### 1.5 合同详情（contractDetail）

合同详情页需支持两种视图切换（Tab）：

**Tab 1 — 条款列表**：现有卡片列表（红黄绿标签，点击展开详情）

**Tab 2 — 原文标注**：完整合同原文 + 高亮标注 + 右侧批注面板

详细实现规格见 `docs/PROMPT-CONTRACT-ANNOTATED-VIEW.md`。

### 2. 合同管理（contracts）

**布局：**
- 顶部：搜索框（左）+ 类型筛选下拉 + 风险筛选下拉（右）+ 上传按钮
- 主体：合同列表表格（名称、类型、风险等级徽章、评分、风险分布条、使用模型、日期）

**交互：**
- 搜索实时过滤
- 筛选下拉联动表格
- 行点击跳转到分析详情页（/contracts/:id）
- 上传按钮打开文件选择对话框
- 数据从 `/api/contracts` 获取（支持 query 参数筛选）

### 3. 知识库管理（knowledge）

**布局：**
- 顶部：标题 + "新增规则"按钮
- Tab 栏：规则库 | 法规库 | 待审核 | 统计

**Tab 1 — 规则库：**
- 搜索框 + 类别筛选下拉
- 规则表格（规则内容、类别徽章、置信度进度条、来源、使用次数、启用开关）
- 开关切换调用 `/api/knowledge/rules/:id` 的 PATCH 接口

**Tab 2 — 法规库：**
- 卡片网格，每个法规一张卡片（名称、条文数、标签）

**Tab 3 — 待审核：**
- 表格（规则内容、来源、置信度、操作按钮）
- 通过/拒绝按钮调用审核 API

**Tab 4 — 统计：**
- 4 个统计卡片
- 规则使用频率条形图

### 4. 同步管理（sync）

**布局：**
- 顶部：3 个同步服务连接卡片（WebDAV / Git / S3），每个带启用开关
- 左侧（2/3）：选中服务的配置表单
- 右侧（1/3）：同步历史时间线 + 手动同步按钮

**交互：**
- 点击连接卡片切换右侧配置表单
- 开关控制启用/禁用
- 测试连接按钮
- 同步历史从 `/api/sync/log` 获取

### 5. 设置（settings）

**布局：**
- LLM 配置区：
  - 远程 API 配置（启用开关、提供商选择、Base URL、API Key、三个模型输入）
  - 本地 Ollama 配置（启用开关、地址、三个模型输入）
- 客户端连接表格（设备名、类型、状态点、IP、最近活跃）
- 数据管理按钮组（导出、备份、重建索引、清除）
- 关于信息

## 设计系统关键变量（从 styles.css 提取）

### 颜色 — 亮色主题
```
--bg-app: #ffffff
--bg-sidebar: #f7f7f5
--bg-surface: #ffffff
--bg-surface-hover: #f7f7f5
--bg-surface-active: #efefed
--bg-muted: #f1f1ef
--text-primary: #1a1a1a
--text-secondary: #6b6b6b
--text-tertiary: #9b9b9b
--border-default: #e8e8e5
--accent: #2383e2
--risk-red: #e53e3e
--risk-yellow: #d69e2e
--risk-green: #38a169
```

### 颜色 — 暗色主题
```
--bg-app: #191919
--bg-sidebar: #202020
--bg-surface: #232323
--text-primary: #ebebeb
--text-secondary: #999999
--border-default: #333333
--accent: #529cca
```

### 间距
```
--sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px;
--sp-5: 20px; --sp-6: 24px; --sp-8: 32px; --sp-10: 40px;
```

### 圆角
```
--radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px; --radius-xl: 12px;
```

### 字体
```
--font-sans: 'Inter', -apple-system, 'SF Pro Text', 'PingFang SC', 'Noto Sans SC', system-ui, sans-serif;
```

## 后端 API 端点（前端需要对接）

```bash
# 合同
GET    /api/contracts              # 合同列表（支持 ?search=&type=&risk=）
GET    /api/contracts/:id          # 合同详情 + 分析结果
POST   /api/contracts/analyze      # 上传并分析合同（multipart/form-data）
POST   /api/contracts/:id/feedback # 提交用户反馈

# 知识库
GET    /api/knowledge/rules        # 规则列表（支持 ?category=&search=）
POST   /api/knowledge/rules        # 新增规则
PUT    /api/knowledge/rules/:id    # 更新规则
DELETE /api/knowledge/rules/:id    # 删除规则
GET    /api/knowledge/stats        # 知识库统计

# 同步
GET    /api/sync/config            # 获取同步配置
PUT    /api/sync/config            # 更新同步配置
POST   /api/sync/push              # 手动上传
POST   /api/sync/pull              # 手动下载
GET    /api/sync/log               # 同步历史

# 设置
GET    /api/settings/llm           # 获取 LLM 配置
PUT    /api/settings/llm           # 更新 LLM 配置
GET    /api/devices                # 连接设备列表

# WebSocket
WS     /ws/client                  # 实时通信（分析进度推送）
```

## 实现要求

### 路由
使用 hash 路由（`#/dashboard`、`#/contracts` 等），不需要引入路由库。每个页面是一个渲染函数，路由变化时清空主内容区并调用对应页面的渲染函数。

### 主题切换
- `document.documentElement.setAttribute('data-theme', 'dark' | 'light')`
- 切换时更新 CSS 自定义属性，所有组件自动响应
- 用 `localStorage` 记住用户偏好
- 在侧边栏底部或设置页提供切换按钮

### 组件模式
使用渲染函数模式（非模板字符串拼接）：
```javascript
function renderStatCard(label, value, icon) {
  const el = document.createElement('div');
  el.className = 'stat-card';
  el.innerHTML = `...`;
  return el;
}
```

### API 调用
所有 API 调用封装在 `api.js` 中，统一处理错误和 loading 状态。使用 `fetch` API。

### 响应式
- 侧边栏宽度 240px，内容区自适应
- 统计卡片 grid 自动适配（minmax(200px, 1fr)）
- 小屏时详情页单列布局

## 开发顺序

建议按以下顺序实现：

1. **基础设施**：tokens.css + base.css + layout.css + app.js + router.js + theme.js
2. **共享组件**：components.css + components.js + icons.js
3. **仪表盘页面**：dashboard.js + pages.css
4. **合同管理页面**：contracts.js
5. **知识库页面**：knowledge.js
6. **同步管理页面**：sync.js
7. **设置页面**：settings.js
8. **API 对接**：api.js，替换 mock 数据为真实 API 调用

## 验证标准

完成后需要检查：
- [ ] 所有 5 个页面可正常切换
- [ ] 亮色/暗色主题切换正常，无闪烁
- [ ] 侧边栏导航高亮正确
- [ ] 表格、卡片、按钮、表单样式一致
- [ ] 风险徽章（红/黄/绿）颜色正确
- [ ] 风险分布条正确显示
- [ ] 搜索和筛选功能可用
- [ ] 无外部 CDN 依赖
- [ ] 所有文本为中文
- [ ] 在 Chrome / Firefox / Safari 中表现一致
