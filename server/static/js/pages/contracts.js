/**
 * 合同管理页面
 */
const ContractsPage = {
  _searchTerm: '',
  _typeFilter: '',
  _riskFilter: '',
  _searchDebounce: null,

  async render(params = {}) {
    // 如果有 id 参数，委托给合同详情页渲染
    if (params.id) {
      return ContractDetailPage.render(params);
    }

    const contracts = await API.contracts.list({
      search: this._searchTerm,
      type: this._typeFilter,
      risk: this._riskFilter,
    });

    // 表格行
    let tableRows = '';
    contracts.forEach(c => {
      const scoreClass = c.score >= 70 ? 'score-green' : c.score >= 50 ? 'score-yellow' : 'score-red';
      tableRows += `<tr class="table-row-clickable" onclick="Router.navigate('contracts/${c.id}')">
        <td style="font-weight:500;display:flex;align-items:center;gap:var(--sp-2)">
          <span class="contract-title" id="title-${c.id}">${Components.escapeHtml(c.title)}</span>
          <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();ContractsPage.editTitle('${c.id}','${Components.escapeHtml(c.title)}')" title="编辑名称" style="opacity:0.5;padding:2px 4px">
            ${Icons.edit(12)}
          </button>
        </td>
        <td class="table-cell-secondary">${Components.escapeHtml(c.type)}</td>
        <td>${Components.RiskBadge(c.riskLevel)}</td>
        <td><span class="${scoreClass}" style="font-weight:600;font-size:var(--text-md)">${c.score}</span></td>
        <td style="min-width:120px">${Components.RiskDistBar(c.redCount, c.yellowCount, c.greenCount)}</td>
        <td class="table-cell-secondary">${Components.escapeHtml(c.model)}</td>
        <td class="table-cell-secondary">${Components.escapeHtml(c.createdAt)}</td>
        <td>
          <button class="btn btn-danger btn-sm btn-icon" onclick="event.stopPropagation();ContractsPage.deleteContract('${c.id}','${Components.escapeHtml(c.title)}')" title="删除合同">
            ${Icons.trash(14)}
          </button>
        </td>
      </tr>`;
    });

    return `
      <div class="content-header animate-in" style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div class="content-title">合同管理</div>
          <div class="content-subtitle">查看和管理所有已分析的合同</div>
        </div>
        <button class="btn btn-primary" onclick="document.getElementById('contract-file-input').click()">
          ${Icons.upload(14)} 上传合同
        </button>
        <input type="file" id="contract-file-input" accept=".pdf,.jpg,.jpeg,.png" style="display:none" onchange="ContractsPage.handleUpload(this)">
      </div>
      <div class="content-body animate-in">
        <div class="filter-bar">
          <div class="search-input-wrapper" style="flex:1">
            <span class="search-icon">${Icons.search(16)}</span>
            <input class="input" placeholder="搜索合同名称..." value="${Components.escapeHtml(this._searchTerm)}" oninput="ContractsPage.onSearch(this.value)">
          </div>
          <select class="select" onchange="ContractsPage.onTypeFilter(this.value)">
            <option value="">所有类型</option>
            <option value="rental" ${this._typeFilter === 'rental' ? 'selected' : ''}>租赁合同</option>
            <option value="labor" ${this._typeFilter === 'labor' ? 'selected' : ''}>劳动合同</option>
            <option value="renovation" ${this._typeFilter === 'renovation' ? 'selected' : ''}>装修合同</option>
            <option value="outsourcing" ${this._typeFilter === 'outsourcing' ? 'selected' : ''}>外包合同</option>
            <option value="loan" ${this._typeFilter === 'loan' ? 'selected' : ''}>借款合同</option>
            <option value="service" ${this._typeFilter === 'service' ? 'selected' : ''}>服务合同</option>
          </select>
          <select class="select" onchange="ContractsPage.onRiskFilter(this.value)">
            <option value="">所有风险</option>
            <option value="red" ${this._riskFilter === 'red' ? 'selected' : ''}>高风险</option>
            <option value="yellow" ${this._riskFilter === 'yellow' ? 'selected' : ''}>中风险</option>
            <option value="green" ${this._riskFilter === 'green' ? 'selected' : ''}>低风险</option>
          </select>
        </div>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>合同名称</th>
                <th>类型</th>
                <th>风险等级</th>
                <th>评分</th>
                <th>风险分布</th>
                <th>使用模型</th>
                <th>分析日期</th>
                <th style="width:60px">操作</th>
              </tr>
            </thead>
            <tbody>${tableRows}</tbody>
          </table>
        </div>
      </div>`;
  },

  onSearch(value) {
    this._searchTerm = value;
    // 防抖：300ms 内无新输入才执行搜索
    clearTimeout(this._searchDebounce);
    this._searchDebounce = setTimeout(() => {
      App.renderCurrentPage('contracts', {}, { restoreFocus: true, focusSelector: '.search-input-wrapper input', focusValue: value });
    }, 300);
  },

  onTypeFilter(value) {
    this._typeFilter = value;
    App.renderCurrentPage();
  },

  onRiskFilter(value) {
    this._riskFilter = value;
    App.renderCurrentPage();
  },

  handleUpload(input) {
    Components.handleFileUpload(input);
  },

  /** 编辑合同名称 */
  editTitle(contractId, currentTitle) {
    const newTitle = prompt('请输入新的合同名称：', currentTitle);
    if (newTitle === null || newTitle.trim() === '' || newTitle === currentTitle) {
      return;
    }

    API.contracts.update(contractId, { title: newTitle.trim() }).then(res => {
      if (res && res.success) {
        Components.toast('合同名称已更新', 'success');
        App.renderCurrentPage();
      } else {
        Components.toast('更新失败：' + (res?.detail || '未知错误'), 'error');
      }
    }).catch(e => {
      Components.toast('更新失败：' + e.message, 'error');
    });
  },

  /** 删除合同 */
  async deleteContract(contractId, contractTitle) {
    if (!confirm(`确定要删除合同「${contractTitle}」吗？此操作不可恢复。`)) {
      return;
    }
    try {
      const res = await API.contracts.delete(contractId);
      if (res && res.success) {
        Components.toast('合同已删除', 'success');
        // 重新渲染当前页面（保持搜索/筛选状态）
        App.renderCurrentPage();
      } else {
        Components.toast('删除失败：' + (res?.detail || '未知错误'), 'error');
      }
    } catch (e) {
      Components.toast('删除失败：' + e.message, 'error');
    }
  }
};
