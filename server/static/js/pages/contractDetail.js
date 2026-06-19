/**
 * 合同详情页面 — 条款列表 + 原文标注视图
 */
const ContractDetailPage = {

  // ── 模块状态 ──
  _contract: null,
  _currentView: 'annotated',  // 'list' | 'annotated'
  _activeClauseId: null,
  _riskFilter: null,
  _riskClauses: [],           // 仅 red + yellow 条款（用于导航）

  async render(params = {}) {
    const id = params.id;
    if (!id) {
      return `
        <div class="content-header animate-in">
          <div class="content-title">合同详情</div>
        </div>
        <div class="content-body animate-in">
          <div class="empty-state">未指定合同</div>
        </div>`;
    }

    const contract = await API.contracts.get(id);
    if (!contract) {
      return `
        <div class="content-header animate-in">
          <div class="content-title">合同详情</div>
        </div>
        <div class="content-body animate-in">
          <div class="empty-state">合同不存在</div>
        </div>`;
    }

    // 保存到模块状态
    this._contract = contract;
    this._activeClauseId = null;
    this._riskFilter = null;
    this._riskClauses = (contract.clauses || []).filter(c => c.riskLevel === 'red' || c.riskLevel === 'yellow');

    // 如果没有 fullText，强制使用列表视图
    if (!contract.fullText) {
      this._currentView = 'list';
    } else {
      this._currentView = 'annotated';
    }

    const scoreClass = contract.score >= 70 ? 'score-green' : contract.score >= 50 ? 'score-yellow' : 'score-red';
    const red = contract.redCount || 0;
    const yellow = contract.yellowCount || 0;
    const green = contract.greenCount || 0;

    return `
      <div class="content-header animate-in" style="padding-bottom:0">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <div style="display:flex;align-items:center;gap:var(--sp-2);margin-bottom:var(--sp-1)">
              <button class="btn btn-ghost btn-sm" onclick="Router.navigate('contracts')" style="margin-left:-8px">${Icons.chevronRight(16)} 返回</button>
            </div>
            <div style="display:flex;align-items:center;gap:var(--sp-2)">
              <div class="content-title">${Components.escapeHtml(contract.title)}</div>
              <button class="btn btn-ghost btn-sm" onclick="ContractDetailPage._editTitle()" title="编辑名称" style="padding:4px 8px">
                ${Icons.edit(14)}
              </button>
            </div>
            <div class="content-subtitle">${Components.escapeHtml(contract.type)} · ${Components.escapeHtml(contract.createdAt)}</div>
          </div>
          <div style="display:flex;align-items:center;gap:var(--sp-4)">
            <button class="btn btn-danger btn-sm" onclick="ContractDetailPage._deleteContract()" title="删除合同">
              ${Icons.trash(14)} 删除
            </button>
            <div class="risk-nav">
              <button class="risk-nav-btn" onclick="ContractDetailPage._navigateRisk(-1)" id="risk-prev">${Icons.chevronRight(16)} 上一条</button>
              <span class="risk-nav-count" id="risk-count">${this._riskClauses.length > 0 ? '1/' + this._riskClauses.length : '—'}</span>
              <button class="risk-nav-btn" onclick="ContractDetailPage._navigateRisk(1)" id="risk-next">下一条 ${Icons.chevronRight(16)}</button>
            </div>
            ${Components.RiskBadge(contract.riskLevel)}
            <span class="${scoreClass}" style="font-size:var(--text-2xl);font-weight:700">${contract.score}</span>
          </div>
        </div>
        <div style="margin:var(--sp-3) 0">
          ${Components.RiskDistInteractive(red, yellow, green, this._riskFilter, 'ContractDetailPage._toggleRiskFilter')}
        </div>
        <div class="view-tabs">
          <div class="view-tab ${this._currentView === 'list' ? 'active' : ''}" onclick="ContractDetailPage._switchView('list')">条款列表</div>
          <div class="view-tab ${this._currentView === 'annotated' ? 'active' : ''}" onclick="ContractDetailPage._switchView('annotated')" ${!contract.fullText ? 'style="opacity:0.4;pointer-events:none"' : ''}>原文标注</div>
        </div>
      </div>
      <div class="content-body animate-in" style="display:flex;overflow:hidden">
        <div id="detail-view-container" style="flex:1;overflow-y:auto;display:flex;flex-direction:column">
          ${this._renderViewContent()}
        </div>
        <div id="annotation-panel" class="annotation-panel collapsed"></div>
      </div>`;
  },

  // ── 视图内容渲染 ──

  _renderViewContent() {
    if (this._currentView === 'annotated') {
      return this._renderAnnotatedView();
    }
    return this._renderListView();
  },

  /** 条款列表视图 */
  _renderListView() {
    const contract = this._contract;
    if (!contract.clauses || contract.clauses.length === 0) {
      return `<div class="empty-state" style="padding:var(--sp-8)">
        ${Icons.shield(48)}
        <p style="color:var(--text-secondary)">暂无条款分析结果</p>
      </div>`;
    }

    const clauses = this._riskFilter
      ? contract.clauses.filter(c => c.riskLevel === this._riskFilter)
      : contract.clauses;

    return `<div style="padding:var(--sp-6)">
      <div class="clause-list">
        ${clauses.map(clause => {
          const riskColor = clause.riskLevel === 'red' ? 'var(--risk-red)' :
                           clause.riskLevel === 'yellow' ? 'var(--risk-yellow)' : 'var(--risk-green)';
          const riskLabel = clause.riskLevel === 'red' ? '高风险' :
                           clause.riskLevel === 'yellow' ? '中风险' : '低风险';
          const isActive = this._activeClauseId === clause.id;
          return `
            <div class="clause-item" style="border-left:3px solid ${riskColor};padding:var(--sp-4);margin-bottom:var(--sp-3);background:var(--bg-surface);border-radius:0 var(--radius-sm) var(--radius-sm) 0;cursor:pointer;transition:all .15s;${isActive ? 'box-shadow:0 0 0 2px var(--accent);' : ''}"
                 onclick="ContractDetailPage._selectClause('${clause.id}')"
                 onmouseenter="this.style.background='var(--bg-surface-hover)'" onmouseleave="this.style.background='var(--bg-surface)'">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-2)">
                <div style="font-weight:600">${Components.escapeHtml(clause.clauseNumber || '条款')}</div>
                ${Components.RiskBadge(clause.riskLevel)}
              </div>
              <div style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--sp-2)">${Components.escapeHtml(clause.clauseTitle || '')}</div>
              <div style="font-size:var(--text-sm);margin-bottom:var(--sp-2)">${Components.escapeHtml(clause.riskSummary || '本维度无明显风险')}</div>
              ${clause.suggestedClause ? `
                <div style="font-size:var(--text-sm);color:var(--accent);background:var(--accent-subtle);padding:var(--sp-2);border-radius:var(--radius-sm);border-left:3px solid var(--accent)">
                  <strong>修改建议：</strong>${Components.escapeHtml(clause.suggestedClause.length > 100 ? clause.suggestedClause.slice(0, 100) + '...' : clause.suggestedClause)}
                </div>
              ` : ''}
              ${clause.legalBasis ? `
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);margin-top:var(--sp-2);font-style:italic">
                  法律依据：${Components.escapeHtml(clause.legalBasis)}
                </div>
              ` : ''}
            </div>
          `;
        }).join('')}
      </div>
    </div>`;
  },

  /** 原文标注视图 */
  _renderAnnotatedView() {
    const contract = this._contract;
    if (!contract.fullText) {
      return `<div class="empty-state" style="padding:var(--sp-8)">
        ${Icons.shield(48)}
        <p style="color:var(--text-secondary)">暂无合同原文</p>
      </div>`;
    }

    const annotatedHtml = this._renderAnnotatedText(contract.fullText, contract.clauses || []);
    return `<div class="original-text" id="original-text">${annotatedHtml}</div>`;
  },

  /**
   * 核心：原文标注渲染算法
   * 在 fullText 中定位每条条款并用高亮 <span> 包裹
   */
  _renderAnnotatedText(fullText, clauses) {
    if (!fullText || !clauses.length) return this._escapeHtml(fullText || '');

    // 0. 标准化 OCR 原文，修复乱换行和乱缩进
    const text = this._normalizeOcrText(fullText);

    // 1. 对每条 clause 定位在标准化后文本中的位置
    const segments = [];
    for (const clause of clauses) {
      const pos = this._locateClause(text, clause);
      if (pos) {
        segments.push({ start: pos.start, end: pos.end, clause });
      }
    }

    // 2. 按起始位置排序
    segments.sort((a, b) => a.start - b.start);

    // 3. 处理重叠：重叠区域取风险等级更高的
    const merged = this._mergeOverlapping(segments);

    // 4. 生成 HTML
    let html = '';
    let cursor = 0;
    for (const seg of merged) {
      // 普通文本
      if (seg.start > cursor) {
        html += this._escapeHtml(text.slice(cursor, seg.start));
      }
      // 高亮文本
      const segText = text.slice(seg.start, seg.end);
      const level = seg.clause.riskLevel;
      const isActive = this._activeClauseId === seg.clause.id;
      const label = seg.clause.clauseNumber || '';
      html += `<span class="clause-mark ${level} ${isActive ? 'active' : ''}" data-clause-id="${seg.clause.id}" onclick="ContractDetailPage._selectClause('${seg.clause.id}')"><span class="clause-label">${label}</span>${this._escapeHtml(segText)}</span>`;
      cursor = seg.end;
    }

    // 剩余文本
    if (cursor < text.length) {
      html += this._escapeHtml(text.slice(cursor));
    }

    return html;
  },

  /** 定位条款在原文中的位置 */
  _locateClause(fullText, clause) {
    // 策略1：clauseNumber + clauseTitle 组合搜索（标准化后换行变空格）
    if (clause.clauseNumber && clause.clauseTitle) {
      const anchors = [
        clause.clauseNumber + ' ' + clause.clauseTitle,  // 标准化后的格式
        clause.clauseNumber + '\n' + clause.clauseTitle,  // 原始格式
      ];
      for (const anchor of anchors) {
        const idx = fullText.indexOf(anchor);
        if (idx !== -1) {
          const contentLen = clause.clauseContent
            ? this._normalizeOcrText(clause.clauseContent).length
            : anchor.length;
          return { start: idx, end: Math.min(idx + contentLen, fullText.length) };
        }
      }
    }

    // 策略2：clauseNumber 搜索
    if (clause.clauseNumber) {
      const numPatterns = [
        clause.clauseNumber,
        clause.clauseNumber.replace(/\s+/g, ''),
      ];
      for (const pat of numPatterns) {
        const idx = fullText.indexOf(pat);
        if (idx !== -1) {
          const contentLen = clause.clauseContent
            ? this._normalizeOcrText(clause.clauseContent).length
            : 200;
          return { start: idx, end: Math.min(idx + contentLen, fullText.length) };
        }
      }
    }

    // 策略3：clauseContent 前 30 字符子串匹配（忽略空白差异）
    if (clause.clauseContent && clause.clauseContent.length >= 10) {
      // 将 clauseContent 标准化后搜索，避免空白差异导致索引偏移
      const normalizedContent = this._normalizeOcrText(clause.clauseContent);
      const snippet = normalizedContent.slice(0, 30);
      const idx = fullText.indexOf(snippet);
      if (idx !== -1) {
        return { start: idx, end: Math.min(idx + normalizedContent.length, fullText.length) };
      }
    }

    return null; // 定位失败，跳过
  },

  /** 合并重叠的高亮片段，重叠区域取更高风险等级 */
  _mergeOverlapping(segments) {
    if (segments.length === 0) return [];

    const riskPriority = { red: 3, yellow: 2, green: 1 };
    const result = [];

    for (const seg of segments) {
      if (result.length === 0) {
        result.push({ ...seg });
        continue;
      }

      const last = result[result.length - 1];
      if (seg.start < last.end) {
        // 有重叠 — 取风险等级更高的
        if ((riskPriority[seg.clause.riskLevel] || 0) > (riskPriority[last.clause.riskLevel] || 0)) {
          // 如果新片段更长，扩展范围
          if (seg.end > last.end) {
            last.end = seg.end;
          }
          last.clause = seg.clause;
        } else {
          // 保留原有，但可能扩展范围
          if (seg.end > last.end) {
            last.end = seg.end;
          }
        }
      } else {
        result.push({ ...seg });
      }
    }

    return result;
  },

  /** HTML 转义（委托给全局 Components.escapeHtml） */
  _escapeHtml(str) {
    return Components.escapeHtml(str);
  },

  /**
   * 标准化 OCR 原文：修复乱换行和乱缩进
   * - 2+ 连续换行 → 段落分隔（保留）
   * - 单换行（行内）→ 合并为空格（OCR 断行）
   * - 多个空格 → 单个空格
   */
  _normalizeOcrText(text) {
    if (!text) return '';
    return text
      .replace(/\n{3,}/g, '\n\n')   // 最多保留两个换行（段落间隔）
      .replace(/([^\n])\n([^\n])/g, '$1 $2')  // 单换行→空格（行内断行）
      .replace(/ {2,}/g, ' ')        // 多空格→单空格
      .trim();
  },

  // ── 批注面板渲染 ──

  _renderAnnoPanel(clause) {
    if (!clause) return '';

    let sections = '';

    // 问题摘要
    if (clause.riskSummary) {
      sections += `
        <div class="anno-section">
          <div class="anno-section-title">问题摘要</div>
          <div class="anno-section-content">${Components.escapeHtml(clause.riskSummary)}</div>
        </div>`;
    }

    // 通俗解释
    if (clause.plainExplanation) {
      sections += `
        <div class="anno-section">
          <div class="anno-section-title">通俗解释</div>
          <div class="anno-section-content">${Components.escapeHtml(clause.plainExplanation)}</div>
        </div>`;
    }

    // 法律依据
    if (clause.legalBasis) {
      sections += `
        <div class="anno-section">
          <div class="anno-section-title">法律依据</div>
          <div class="anno-section-content legal">${Components.escapeHtml(clause.legalBasis)}</div>
        </div>`;
    }

    // 修改建议
    if (clause.suggestedClause) {
      sections += `
        <div class="anno-section">
          <div class="anno-section-title">修改建议</div>
          <div class="anno-section-content suggest">${Components.escapeHtml(clause.suggestedClause)}</div>
        </div>`;
    }

    // 严重度
    if (clause.severityScore) {
      sections += `
        <div class="anno-section">
          <div class="anno-section-title">严重度</div>
          ${Components.SeverityBar(clause.severityScore)}
        </div>`;
    }

    // 反馈按钮（非绿色条款）
    let feedbackHtml = '';
    if (clause.riskLevel !== 'green') {
      const fb = clause.userFeedback;
      feedbackHtml = `
        <div class="anno-feedback">
          <button class="btn btn-sm ${fb === 'correct' ? 'btn-primary' : 'btn-secondary'}"
                  onclick="ContractDetailPage._submitFeedback('${clause.id}', 'correct')"
                  ${fb === 'correct' ? 'disabled' : ''}>标注准确</button>
          <button class="btn btn-sm ${fb === 'incorrect' ? 'btn-danger' : 'btn-secondary'}"
                  onclick="ContractDetailPage._submitFeedback('${clause.id}', 'incorrect')"
                  ${fb === 'incorrect' ? 'disabled' : ''}>标注不准确</button>
        </div>`;
    }

    return `
      <div class="anno-header">
        <div style="display:flex;align-items:center;gap:var(--sp-2);min-width:0">
          ${Components.RiskBadge(clause.riskLevel)}
          <span style="font-weight:600;font-size:var(--text-sm);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${Components.escapeHtml(clause.clauseTitle || clause.clauseNumber || '条款')}</span>
        </div>
        <div class="anno-close" onclick="ContractDetailPage._closeAnnotation()">${Icons.x(16)}</div>
      </div>
      <div class="anno-body">
        ${sections || '<div style="color:var(--text-tertiary);font-size:var(--text-sm)">暂无详细分析</div>'}
        ${feedbackHtml}
      </div>`;
  },

  // ── 全局交互函数（供 inline onclick 调用）──

  /** 切换视图 */
  _switchView(view) {
    if (view === this._currentView) return;
    if (view === 'annotated' && !this._contract.fullText) return;
    this._currentView = view;
    this._activeClauseId = null;
    this._closeAnnotation();

    // 更新 Tab 样式
    document.querySelectorAll('.view-tab').forEach(tab => {
      tab.classList.toggle('active', tab.textContent.includes(view === 'list' ? '条款列表' : '原文标注'));
    });

    // 重渲染内容区
    const container = document.getElementById('detail-view-container');
    if (container) {
      container.innerHTML = this._renderViewContent();
      container.scrollTop = 0;
    }
  },

  /** 选中条款 */
  _selectClause(clauseId) {
    const clause = (this._contract.clauses || []).find(c => c.id === clauseId);
    if (!clause) return;

    this._activeClauseId = clauseId;

    // 更新高亮状态
    document.querySelectorAll('.clause-mark').forEach(el => {
      el.classList.toggle('active', el.dataset.clauseId === clauseId);
    });

    // 更新列表卡片激活状态
    document.querySelectorAll('.clause-item').forEach(el => {
      // 通过 onclick 属性中的 clauseId 匹配
    });

    // 打开批注面板
    const panel = document.getElementById('annotation-panel');
    if (panel) {
      panel.classList.remove('collapsed');
      panel.innerHTML = this._renderAnnoPanel(clause);
    }

    // 滚动到高亮位置
    if (this._currentView === 'annotated') {
      const mark = document.querySelector(`.clause-mark[data-clause-id="${clauseId}"]`);
      if (mark) {
        mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    // 更新导航计数
    this._updateNavCount();
  },

  /** 关闭批注面板 */
  _closeAnnotation() {
    this._activeClauseId = null;
    const panel = document.getElementById('annotation-panel');
    if (panel) {
      panel.classList.add('collapsed');
      panel.innerHTML = '';
    }
    // 清除高亮
    document.querySelectorAll('.clause-mark.active').forEach(el => el.classList.remove('active'));
  },

  /** 风险导航：上一条/下一条 */
  _navigateRisk(direction) {
    const clauses = this._riskClauses;
    if (clauses.length === 0) return;

    let idx = clauses.findIndex(c => c.id === this._activeClauseId);
    if (idx === -1) {
      // 没有激活条款，跳到第一条
      idx = direction > 0 ? 0 : clauses.length - 1;
    } else {
      idx += direction;
      if (idx < 0) idx = clauses.length - 1;
      if (idx >= clauses.length) idx = 0;
    }

    this._selectClause(clauses[idx].id);
  },

  /** 更新导航计数 */
  _updateNavCount() {
    const el = document.getElementById('risk-count');
    if (!el) return;
    const clauses = this._riskClauses;
    if (clauses.length === 0) {
      el.textContent = '—';
      return;
    }
    const idx = clauses.findIndex(c => c.id === this._activeClauseId);
    el.textContent = `${idx >= 0 ? idx + 1 : 1}/${clauses.length}`;
  },

  /** 风险分布条筛选 */
  _toggleRiskFilter(level) {
    // 点击已选中的则取消筛选
    this._riskFilter = this._riskFilter === level ? null : level;

    // 更新分布条样式
    const container = document.querySelector('.risk-dist-interactive');
    if (container) {
      container.parentElement.outerHTML = Components.RiskDistInteractive(
        this._contract.redCount || 0,
        this._contract.yellowCount || 0,
        this._contract.greenCount || 0,
        this._riskFilter,
        'ContractDetailPage._toggleRiskFilter'
      );
    }

    // 重渲染内容
    const viewContainer = document.getElementById('detail-view-container');
    if (viewContainer) {
      viewContainer.innerHTML = this._renderViewContent();
    }
  },

  /** 提交反馈 */
  async _submitFeedback(clauseId, feedback) {
    try {
      await API.contracts.feedback(this._contract.id, clauseId, feedback);

      // 更新本地数据
      const clause = (this._contract.clauses || []).find(c => c.id === clauseId);
      if (clause) clause.userFeedback = feedback;

      // 刷新批注面板
      if (this._activeClauseId === clauseId) {
        const panel = document.getElementById('annotation-panel');
        if (panel) {
          panel.innerHTML = this._renderAnnoPanel(clause);
        }
      }

      Components.toast(feedback === 'correct' ? '已标注为准确' : '已标注为不准确', 'success');
    } catch (e) {
      Components.toast('提交失败：' + e.message, 'error');
    }
  },

  /** 编辑合同名称 */
  async _editTitle() {
    const contract = this._contract;
    if (!contract) return;

    const newTitle = prompt('请输入新的合同名称：', contract.title);
    if (newTitle === null || newTitle.trim() === '' || newTitle === contract.title) {
      return;
    }

    try {
      const res = await API.contracts.update(contract.id, { title: newTitle.trim() });
      if (res && res.success) {
        // 更新本地数据
        contract.title = newTitle.trim();
        // 更新页面显示
        const titleEl = document.querySelector('.content-title');
        if (titleEl) titleEl.textContent = newTitle.trim();
        // 更新浏览器标题
        document.title = `${newTitle.trim()} - 合同红绿灯`;
        Components.toast('合同名称已更新', 'success');
      } else {
        Components.toast('更新失败：' + (res?.detail || '未知错误'), 'error');
      }
    } catch (e) {
      Components.toast('更新失败：' + e.message, 'error');
    }
  },

  /** 删除合同 */
  async _deleteContract() {
    const contract = this._contract;
    if (!contract) return;
    if (!confirm(`确定要删除合同「${contract.title}」吗？此操作不可恢复。`)) {
      return;
    }
    try {
      const res = await API.contracts.delete(contract.id);
      if (res && res.success) {
        Components.toast('合同已删除', 'success');
        Router.navigate('contracts');
      } else {
        Components.toast('删除失败：' + (res?.detail || '未知错误'), 'error');
      }
    } catch (e) {
      Components.toast('删除失败：' + e.message, 'error');
    }
  },
};
