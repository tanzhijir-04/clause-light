/**
 * 仪表盘页面
 */
const DashboardPage = {
  async render() {
    const contracts = await API.contracts.list();
    const stats = await API.knowledge.stats();
    const devices = await API.connection.devices().catch(() => ({ total: 0, devices: [] }));

    // 最近分析表格
    let tableRows = '';
    contracts.forEach(c => {
      const scoreClass = c.score >= 70 ? 'score-green' : c.score >= 50 ? 'score-yellow' : 'score-red';
      tableRows += `<tr>
        <td style="font-weight:500">${Components.escapeHtml(c.title)}</td>
        <td class="table-cell-secondary">${Components.escapeHtml(c.type)}</td>
        <td><span class="${scoreClass}" style="font-weight:600">${c.score}</span></td>
        <td style="min-width:120px">${Components.RiskDistBar(c.redCount, c.yellowCount, c.greenCount)}</td>
        <td class="table-cell-secondary">${Components.escapeHtml(c.createdAt)}</td>
      </tr>`;
    });

    // 风险分布
    const riskDistHtml = `
      <div class="card">
        <div class="card-header"><h3>风险分布</h3></div>
        <div class="card-body">
          <div class="risk-summary">
            <div class="risk-summary-item">
              <div class="risk-summary-value" style="color:var(--risk-red)">${stats.redCount}</div>
              <div class="risk-summary-label">高风险</div>
            </div>
            <div class="risk-summary-item">
              <div class="risk-summary-value" style="color:var(--risk-yellow)">${stats.yellowCount}</div>
              <div class="risk-summary-label">中风险</div>
            </div>
            <div class="risk-summary-item">
              <div class="risk-summary-value" style="color:var(--risk-green)">${stats.greenCount}</div>
              <div class="risk-summary-label">低风险</div>
            </div>
          </div>
          ${Components.RiskDistBar(stats.redCount, stats.yellowCount, stats.greenCount)}
        </div>
      </div>`;

    // 上传区域
    const uploadHtml = Components.UploadZone();

    return `
      <div class="content-header animate-in">
        <div class="content-title">仪表盘</div>
        <div class="content-subtitle">合同风险审查概览</div>
      </div>
      <div class="content-body animate-in">
        <div class="stats-grid" style="margin-bottom:var(--sp-6)">
          ${Components.StatCard('合同总数', stats.totalContracts, `本月 +${stats.thisMonth}`, 'up', 'fileText')}
          ${Components.StatCard('平均风险分', stats.avgScore, '较上月 +3', 'up', 'barChart')}
          ${Components.StatCard('知识库规则', stats.totalRules, '自动学习 +1', 'up', 'book')}
          ${Components.StatCard('连接设备', devices.total || 0, devices.total > 0 ? `${devices.total} 台在线` : '暂无设备', devices.total > 0 ? 'up' : 'neutral', 'smartphone')}
        </div>

        <div class="dashboard-grid">
          <div class="card">
            <div class="card-header">
              <h3>最近分析</h3>
              <button class="btn btn-ghost btn-sm" onclick="Router.navigate('contracts')">查看全部</button>
            </div>
            <div class="card-body" style="padding:0">
              <table>
                <thead>
                  <tr>
                    <th>合同</th>
                    <th>类型</th>
                    <th>评分</th>
                    <th>风险分布</th>
                    <th>日期</th>
                  </tr>
                </thead>
                <tbody>${tableRows}</tbody>
              </table>
            </div>
          </div>

          <div class="dashboard-right">
            ${riskDistHtml}
            ${uploadHtml}
          </div>
        </div>
      </div>`;
  }
};
