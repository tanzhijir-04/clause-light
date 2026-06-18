# Task 1 Report: 修复搜索输入框失焦问题

**Status:** DONE
**Commit:** `5c860c77` (main)
**Date:** 2026-06-18

## 问题描述

合同管理页面 (`contracts.js`) 和知识库管理页面 (`knowledge.js`) 的搜索输入框在每次按键时都会失焦，导致用户无法连续输入搜索关键词。

**根本原因：** `onSearch()` 在每次按键时直接调用 `App.renderCurrentPage()`，该函数重新渲染整个页面 HTML（包括侧边栏），销毁了搜索输入框的 DOM 元素并重建，焦点自然丢失。

## 修复方案

### 1. 防抖搜索（contracts.js + knowledge.js）

- 在两个页面对象中添加 `_searchDebounce: null` 变量
- `onSearch()` 改为 300ms 防抖：每次按键先清除上一个定时器，设置新的 300ms 延迟
- 只有用户停止输入 300ms 后才触发页面重渲染，大幅减少不必要的渲染次数

### 2. 焦点恢复（app.js）

- `renderPage()` 新增 `renderOptions` 参数（第三个参数），默认值 `{}`
- `renderCurrentPage()` 签名扩展为 `(route, params, renderOptions)`，所有参数均有默认值，完全向后兼容
- 当 `renderOptions.restoreFocus === true` 且 `renderOptions.focusSelector` 存在时，渲染完成后通过 `requestAnimationFrame` 找到目标输入框并调用 `.focus()` + `.setSelectionRange(len, len)` 将光标定位到末尾

### 3. 搜索输入框渲染保持 value 同步

- 两个页面的搜索输入框 HTML 已有 `value="${this._searchTerm}"`，搜索词在 `onSearch` 中先更新到 `_searchTerm`，重渲染后输入框值自动同步

## 修改文件

| 文件 | 改动内容 |
|------|----------|
| `server/static/js/pages/contracts.js` | 添加 `_searchDebounce` 变量；`onSearch()` 改为防抖 300ms |
| `server/static/js/pages/knowledge.js` | 添加 `_searchDebounce` 变量；`onSearch()` 改为防抖 300ms |
| `server/static/js/app.js` | `renderPage()` 增加 `renderOptions` 参数；添加焦点恢复逻辑；`renderCurrentPage()` 签名扩展 |

## 向后兼容性

- `renderCurrentPage()` 所有新参数均有默认值，现有调用方（sync.js 等）无需修改
- `renderPage()` 的 `renderOptions` 默认为空对象，不影响非搜索场景的渲染

## 验证方式

1. 启动服务器，访问合同管理页面
2. 在搜索框中连续快速输入文字，验证输入框保持焦点、光标不跳动
3. 等待 300ms 防抖后验证搜索结果正确更新
4. 在知识库管理页面重复上述测试
5. 验证其他页面（仪表盘、同步、设置等）功能不受影响
