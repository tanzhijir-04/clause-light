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
        <td style="font-weight:500">${c.title}</td>
        <td class="table-cell-secondary">${c.type}</td>
        <td>${Components.RiskBadge(c.riskLevel)}</td>
        <td><span class="${scoreClass}" style="font-weight:600;font-size:var(--text-md)">${c.score}</span></td>
        <td style="min-width:120px">${Components.RiskDistBar(c.redCount, c.yellowCount, c.greenCount)}</td>
        <td class="table-cell-secondary">${c.model}</td>
        <td class="table-cell-secondary">${c.createdAt}</td>
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
            <input class="input" placeholder="搜索合同名称..." value="${this._searchTerm}" oninput="ContractsPage.onSearch(this.value)">
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
  }
};
