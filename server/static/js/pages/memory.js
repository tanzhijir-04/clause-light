/**
 * 分层记忆浏览与反馈页面
 */
const MemoryPage = {
  _searchTerm: '',
  _searchDebounce: null,

  async render() {
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
      <div class="content-header animate-in">
        <div>
          <div class="content-title">分层记忆</div>
          <div class="content-subtitle">浏览 L1 记忆原子，并对召回内容确认或纠错</div>
        </div>
      </div>
      <div class="content-body animate-in">
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
        </div>
      </div>`;
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
};
