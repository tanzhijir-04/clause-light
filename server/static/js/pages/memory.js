/**
 * 分层记忆浏览、反馈与资产待审页面
 */
const MemoryPage = {
  _tab: 'atoms',
  _searchTerm: '',
  _searchDebounce: null,

  async render() {
    const tabs = [
      { key: 'atoms', label: '记忆原子' },
      { key: 'pending', label: '待审' },
    ];
    const tabsHtml = tabs.map(t =>
      `<div class="tab ${this._tab === t.key ? 'active' : ''}" onclick="MemoryPage.switchTab('${t.key}')">${t.label}</div>`
    ).join('');

    let contentHtml = '';
    if (this._tab === 'pending') {
      contentHtml = await this._renderPendingTab();
    } else {
      contentHtml = await this._renderAtomsTab();
    }

    return `
      <div class="content-header animate-in">
        <div>
          <div class="content-title">分层记忆</div>
          <div class="content-subtitle">浏览 L1 记忆原子，审核自动提炼的规则 / Skill / Wiki</div>
        </div>
      </div>
      <div class="content-body animate-in">
        <div class="tabs">${tabsHtml}</div>
        ${contentHtml}
      </div>`;
  },

  async _renderAtomsTab() {
    const atoms = await API.memory.atoms({
      q: this._searchTerm,
      status: 'active',
    });

    let tableRows = '';
    if (!atoms || atoms.length === 0) {
      tableRows = `<tr><td colspan="5" class="table-cell-secondary" style="text-align:center;padding:var(--sp-6)">暂无活跃记忆原子</td></tr>`;
    } else {
      atoms.forEach(a => {
        const kindLabel = { fact: '事实', preference: '偏好', constraint: '约束', event: '事件' }[a.kind] || a.kind;
        tableRows += `<tr>
          <td class="rule-text-cell">${Components.escapeHtml(a.content || '')}</td>
          <td><span class="risk-badge" style="background:var(--accent-subtle);color:var(--accent);border:1px solid var(--accent)">${Components.escapeHtml(kindLabel)}</span></td>
          <td class="table-cell-secondary">${Components.escapeHtml(a.contract_type || '—')}</td>
          <td>
            <div class="confidence-cell">
              <div class="progress-bar confidence-bar"><div class="progress-bar-fill accent" style="width:${(a.confidence || 0) * 100}%"></div></div>
              <span class="table-cell-secondary">${((a.confidence || 0) * 100).toFixed(0)}%</span>
            </div>
          </td>
          <td style="white-space:nowrap">
            <button class="btn btn-sm" onclick="MemoryPage.confirmAtom('${a.id}')">${Icons.check(14)} 确认</button>
            <button class="btn btn-sm" onclick="MemoryPage.rejectAtom('${a.id}')">${Icons.x(14)} 拒绝</button>
          </td>
        </tr>`;
      });
    }

    return `
      <div style="display:flex;gap:var(--sp-3);margin-bottom:var(--sp-4)">
        <div class="search-input-wrapper" style="flex:1">
          <span class="search-icon">${Icons.search(16)}</span>
          <input class="input" placeholder="搜索记忆内容..." value="${Components.escapeHtml(this._searchTerm)}" oninput="MemoryPage.onSearch(this.value)">
        </div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>内容</th>
              <th>类型</th>
              <th>合同类型</th>
              <th>置信度</th>
              <th>反馈</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>`;
  },

  async _renderPendingTab() {
    const pending = await API.memory.pending();
    const typeLabel = { rule: '规则', atom: '原子', skill: 'Skill', wiki: 'Wiki' };

    let tableRows = '';
    if (!pending || pending.length === 0) {
      tableRows = `<tr><td colspan="5" class="table-cell-secondary" style="text-align:center;padding:var(--sp-6)">暂无待审资产</td></tr>`;
    } else {
      pending.forEach(item => {
        const type = item.asset_type || '';
        const id = item.id || '';
        tableRows += `<tr>
          <td><span class="risk-badge" style="background:var(--accent-subtle);color:var(--accent);border:1px solid var(--accent)">${Components.escapeHtml(typeLabel[type] || type)}</span></td>
          <td class="table-cell-secondary" style="font-family:var(--font-mono);font-size:var(--text-xs)">${Components.escapeHtml(id)}</td>
          <td class="rule-text-cell">${Components.escapeHtml(item.summary || '')}</td>
          <td class="table-cell-secondary">${(((item.confidence || 0) * 100).toFixed(0))}%</td>
          <td style="white-space:nowrap">
            <button class="btn btn-sm btn-primary" onclick="MemoryPage.approvePending('${type}','${id}')">${Icons.check(12)} 通过</button>
            <button class="btn btn-sm btn-ghost" onclick="MemoryPage.rejectPending('${type}','${id}')">${Icons.x(12)} 拒绝</button>
            <button class="btn btn-sm" onclick="MemoryPage.rollbackPending('${type}','${id}')">回滚</button>
          </td>
        </tr>`;
      });
    }

    return `
      <div class="card">
        <div class="card-header">
          <h3>资产待审队列</h3>
          <span class="table-cell-secondary">${(pending || []).length} 条</span>
        </div>
        <div class="card-body" style="padding:0">
          <table>
            <thead>
              <tr>
                <th>类型</th>
                <th>ID</th>
                <th>摘要</th>
                <th>置信度</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>${tableRows}</tbody>
          </table>
        </div>
      </div>`;
  },

  switchTab(tab) {
    this._tab = tab;
    App.renderCurrentPage();
  },

  onSearch(value) {
    this._searchTerm = value;
    clearTimeout(this._searchDebounce);
    this._searchDebounce = setTimeout(() => {
      App.renderCurrentPage('memory', {}, {
        restoreFocus: true,
        focusSelector: '.search-input-wrapper input',
        focusValue: value,
      });
    }, 300);
  },

  confirmAtom(id) {
    API.memory.feedback({ atom_id: id, confirm: true, payload: {} }).then(res => {
      if (res && res.success) App.renderCurrentPage();
    });
  },

  rejectAtom(id) {
    API.memory.feedback({ atom_id: id, confirm: false, payload: {} }).then(res => {
      if (res && res.success) App.renderCurrentPage();
    });
  },

  _refreshPending() {
    // 操作后刷新并保留待审 Tab
    this._tab = 'pending';
    App.renderCurrentPage();
  },

  approvePending(assetType, assetId) {
    API.memory.approvePending(assetType, assetId).then(res => {
      if (res && res.success) this._refreshPending();
    });
  },

  rejectPending(assetType, assetId) {
    API.memory.rejectPending(assetType, assetId).then(res => {
      if (res && res.success) this._refreshPending();
    });
  },

  rollbackPending(assetType, assetId) {
    API.memory.rollbackPending(assetType, assetId).then(res => {
      if (res && res.success) this._refreshPending();
    });
  },
};
