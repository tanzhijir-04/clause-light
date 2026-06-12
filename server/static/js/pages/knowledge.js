/**
 * 知识库管理页面
 */
const KnowledgePage = {
  _tab: 'rules',
  _searchTerm: '',
  _categoryFilter: '',

  async render() {
    const tabs = [
      { key: 'rules', label: '规则库' },
      { key: 'laws', label: '法规库' },
      { key: 'pending', label: '待审核' },
      { key: 'stats', label: '统计' },
    ];

    const tabsHtml = tabs.map(t =>
      `<div class="tab ${this._tab === t.key ? 'active' : ''}" onclick="KnowledgePage.switchTab('${t.key}')">${t.label}</div>`
    ).join('');

    let contentHtml = '';
    if (this._tab === 'rules') {
      contentHtml = await this._renderRulesTab();
    } else if (this._tab === 'laws') {
      contentHtml = await this._renderLawsTab();
    } else if (this._tab === 'pending') {
      contentHtml = await this._renderPendingTab();
    } else if (this._tab === 'stats') {
      contentHtml = await this._renderStatsTab();
    }

    return `
      <div class="content-header animate-in" style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div class="content-title">知识库管理</div>
          <div class="content-subtitle">管理风险审查规则、法规条文和自动学习结果</div>
        </div>
        <button class="btn btn-primary" onclick="KnowledgePage.showAddRuleDialog()">${Icons.plus(14)} 新增规则</button>
      </div>
      <div class="content-body animate-in">
        <div class="tabs">${tabsHtml}</div>
        ${contentHtml}
      </div>`;
  },

  async _renderRulesTab() {
    const rules = await API.knowledge.rules({
      search: this._searchTerm,
      category: this._categoryFilter,
    });

    let tableRows = '';
    rules.forEach(r => {
      const sourceMap = { manual: '手动', auto_learned: '自动学习', user_feedback: '用户反馈' };
      tableRows += `<tr>
        <td class="rule-text-cell">${r.text}</td>
        <td><span class="risk-badge" style="background:var(--accent-subtle);color:var(--accent);border:1px solid var(--accent)">${r.category}</span></td>
        <td>
          <div class="confidence-cell">
            <div class="progress-bar confidence-bar"><div class="progress-bar-fill accent" style="width:${r.confidence * 100}%"></div></div>
            <span class="table-cell-secondary">${(r.confidence * 100).toFixed(0)}%</span>
          </div>
        </td>
        <td class="table-cell-secondary">${sourceMap[r.source] || r.source}</td>
        <td class="table-cell-secondary">${r.usageCount}</td>
        <td>${Components.Toggle('rule-' + r.id, r.active, 'compact')}</td>
      </tr>`;
    });

    // 绑定 toggle 事件
    rules.forEach(r => {
      Components.onToggle('rule-' + r.id, (on) => {
        API.knowledge.updateRule(r.id, { active: on });
      });
    });

    return `
      <div style="display:flex;gap:var(--sp-3);margin-bottom:var(--sp-4)">
        <div class="search-input-wrapper" style="flex:1">
          <span class="search-icon">${Icons.search(16)}</span>
          <input class="input" placeholder="搜索规则..." value="${this._searchTerm}" oninput="KnowledgePage.onSearch(this.value)">
        </div>
        <select class="select" onchange="KnowledgePage.onCategoryFilter(this.value)">
          <option value="">所有类别</option>
          <option value="通用" ${this._categoryFilter === '通用' ? 'selected' : ''}>通用</option>
          <option value="租赁" ${this._categoryFilter === '租赁' ? 'selected' : ''}>租赁</option>
          <option value="劳动" ${this._categoryFilter === '劳动' ? 'selected' : ''}>劳动</option>
          <option value="装修" ${this._categoryFilter === '装修' ? 'selected' : ''}>装修</option>
          <option value="外包" ${this._categoryFilter === '外包' ? 'selected' : ''}>外包</option>
        </select>
      </div>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>规则内容</th>
              <th>类别</th>
              <th>置信度</th>
              <th>来源</th>
              <th>使用次数</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>`;
  },

  async _renderLawsTab() {
    const laws = await API.knowledge.laws();
    const tagColors = ['green', 'yellow', 'red'];

    let cardsHtml = '';
    laws.forEach(law => {
      const tagsHtml = law.tags.slice(0, 3).map((tag, i) => {
        const color = tagColors[i % tagColors.length];
        return `<span class="risk-badge ${color}" style="border:1px solid var(--border-default)">${tag}</span>`;
      }).join('');
      const extraCount = law.tags.length - 3;
      const extraTag = extraCount > 0 ? `<span class="risk-badge" style="background:var(--bg-muted);color:var(--text-secondary);border:1px solid var(--border-default)">+${extraCount}</span>` : '';

      cardsHtml += `
        <div class="card">
          <div class="card-header">
            <h3>${law.name}</h3>
            <span class="table-cell-secondary">${law.articles} 条</span>
          </div>
          <div class="card-body">
            <div style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--sp-3)">
              合同编相关条文，涵盖合同订立、效力、履行、违约责任等
            </div>
            <div style="display:flex;gap:var(--sp-2)">
              ${tagsHtml}${extraTag}
            </div>
          </div>
        </div>`;
    });

    return `<div class="grid-2">${cardsHtml}</div>`;
  },

  async _renderPendingTab() {
    const pending = await API.knowledge.pending();
    const sourceMap = { manual: '手动', auto_learned: '自动学习', user_feedback: '用户反馈' };

    let tableRows = '';
    pending.forEach(r => {
      tableRows += `<tr>
        <td style="font-weight:500">${r.text}</td>
        <td class="table-cell-secondary">${sourceMap[r.source] || r.source}</td>
        <td class="table-cell-secondary">${(r.confidence * 100).toFixed(0)}%</td>
        <td>
          <div style="display:flex;gap:var(--sp-2)">
            <button class="btn btn-sm btn-primary" onclick="KnowledgePage.approveRule('${r.id}')">${Icons.check(12)} 通过</button>
            <button class="btn btn-sm btn-ghost" onclick="KnowledgePage.rejectRule('${r.id}')">${Icons.x(12)} 拒绝</button>
          </div>
        </td>
      </tr>`;
    });

    return `
      <div class="card">
        <div class="card-header">
          <h3>待审核规则</h3>
          <span class="table-cell-secondary">${pending.length} 条待审核</span>
        </div>
        <div class="card-body" style="padding:0">
          <table>
            <thead><tr><th>规则内容</th><th>来源</th><th>置信度</th><th>操作</th></tr></thead>
            <tbody>${tableRows}</tbody>
          </table>
        </div>
      </div>`;
  },

  async _renderStatsTab() {
    const stats = await API.knowledge.stats();
    const rules = await API.knowledge.rules();
    const topRules = rules.sort((a, b) => b.usageCount - a.usageCount).slice(0, 5);

    let barsHtml = '';
    topRules.forEach(r => {
      barsHtml += `
        <div style="display:flex;align-items:center;gap:var(--sp-3);margin-bottom:var(--sp-3)">
          <span style="font-size:var(--text-xs);color:var(--text-secondary);width:180px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.text}</span>
          <div class="progress-bar" style="flex:1"><div class="progress-bar-fill accent" style="width:${(r.usageCount / 45) * 100}%"></div></div>
          <span class="table-cell-secondary" style="width:30px;text-align:right">${r.usageCount}</span>
        </div>`;
    });

    return `
      <div class="knowledge-stats-grid">
        ${Components.StatCard('规则总数', stats.totalRules, '', 'neutral', 'book')}
        ${Components.StatCard('法规条文', stats.totalLaws || 70, '', 'neutral', 'database')}
        ${Components.StatCard('平均置信度', `${(stats.avgConfidence * 100).toFixed(0)}%`, '', 'neutral', 'zap')}
        ${Components.StatCard('待审核', stats.pendingReview || 2, '', 'neutral', 'clock')}
      </div>
      <div class="card">
        <div class="card-header"><h3>规则使用频率</h3></div>
        <div class="card-body">${barsHtml}</div>
      </div>`;
  },

  switchTab(tab) {
    this._tab = tab;
    App.renderCurrentPage();
  },

  onSearch(value) {
    this._searchTerm = value;
    App.renderCurrentPage();
  },

  onCategoryFilter(value) {
    this._categoryFilter = value;
    App.renderCurrentPage();
  },

  showAddRuleDialog() {
    const text = prompt('请输入规则内容：');
    if (text && text.trim()) {
      const category = prompt('类别（通用/租赁/劳动/装修/外包）：') || '通用';
      API.knowledge.createRule({ text: text.trim(), category }).then(res => {
        if (res && res.success) {
          App.renderCurrentPage();
        }
      });
    }
  },

  approveRule(id) {
    API.knowledge.updateRule(id, { status: 'approved' }).then(res => {
      if (res && res.success) App.renderCurrentPage();
    });
  },

  rejectRule(id) {
    API.knowledge.updateRule(id, { status: 'rejected' }).then(res => {
      if (res && res.success) App.renderCurrentPage();
    });
  },
};
