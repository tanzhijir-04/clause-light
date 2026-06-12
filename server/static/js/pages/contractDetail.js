/**
 * 合同详情页面
 */
const ContractDetailPage = {
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

    const scoreClass = contract.score >= 70 ? 'score-green' : contract.score >= 50 ? 'score-yellow' : 'score-red';

    return `
      <div class="content-header animate-in" style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="display:flex;align-items:center;gap:var(--sp-2);margin-bottom:var(--sp-1)">
            <button class="btn btn-ghost btn-sm" onclick="Router.navigate('contracts')" style="margin-left:-8px">${Icons.chevronRight(16)} 返回</button>
          </div>
          <div class="content-title">${contract.title}</div>
          <div class="content-subtitle">${contract.type} · ${contract.createdAt}</div>
        </div>
        <div style="display:flex;align-items:center;gap:var(--sp-4)">
          ${Components.RiskBadge(contract.riskLevel)}
          <span class="${scoreClass}" style="font-size:var(--text-2xl);font-weight:700">${contract.score}</span>
        </div>
      </div>
      <div class="content-body animate-in">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-6);margin-bottom:var(--sp-6)">
          <div class="card">
            <div class="card-header"><h3>风险分布</h3></div>
            <div class="card-body">
              <div class="risk-summary" style="margin-bottom:var(--sp-4)">
                <div class="risk-summary-item">
                  <div class="risk-summary-value" style="color:var(--risk-red)">${contract.redCount}</div>
                  <div class="risk-summary-label">高风险</div>
                </div>
                <div class="risk-summary-item">
                  <div class="risk-summary-value" style="color:var(--risk-yellow)">${contract.yellowCount}</div>
                  <div class="risk-summary-label">中风险</div>
                </div>
                <div class="risk-summary-item">
                  <div class="risk-summary-value" style="color:var(--risk-green)">${contract.greenCount}</div>
                  <div class="risk-summary-label">低风险</div>
                </div>
              </div>
              ${Components.RiskDistBar(contract.redCount, contract.yellowCount, contract.greenCount)}
            </div>
          </div>
          <div class="card">
            <div class="card-header"><h3>分析信息</h3></div>
            <div class="card-body">
              <div style="display:flex;flex-direction:column;gap:var(--sp-3)">
                <div style="display:flex;justify-content:space-between">
                  <span class="table-cell-secondary">使用模型</span>
                  <span style="font-size:var(--text-sm)">${contract.model}</span>
                </div>
                <div style="display:flex;justify-content:space-between">
                  <span class="table-cell-secondary">合同类型</span>
                  <span style="font-size:var(--text-sm)">${contract.type}</span>
                </div>
                <div style="display:flex;justify-content:space-between">
                  <span class="table-cell-secondary">分析状态</span>
                  <span style="font-size:var(--text-sm);color:var(--success)">已完成</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>风险条款分析</h3>
            <span class="table-cell-secondary">共 ${contract.clauses ? contract.clauses.length : 0} 条</span>
          </div>
          <div class="card-body">
            ${contract.clauses && contract.clauses.length > 0 ? `
              <div class="clause-list">
                ${contract.clauses.map(clause => {
                  const riskColor = clause.riskLevel === 'red' ? 'var(--risk-red)' :
                                   clause.riskLevel === 'yellow' ? 'var(--risk-yellow)' : 'var(--risk-green)';
                  const riskLabel = clause.riskLevel === 'red' ? '高风险' :
                                   clause.riskLevel === 'yellow' ? '中风险' : '低风险';
                  return `
                    <div class="clause-item" style="border-left:3px solid ${riskColor};padding:var(--sp-4);margin-bottom:var(--sp-3);background:var(--bg-secondary);border-radius:var(--radius)">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-2)">
                        <div style="font-weight:600">${clause.clauseNumber || '条款'}</div>
                        <span style="color:${riskColor};font-size:var(--text-sm);font-weight:500">${riskLabel}</span>
                      </div>
                      <div style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--sp-2)">${clause.clauseTitle || ''}</div>
                      <div style="font-size:var(--text-sm);margin-bottom:var(--sp-2)">${clause.riskSummary || '本维度无明显风险'}</div>
                      ${clause.suggestedClause ? `
                        <div style="font-size:var(--text-sm);color:var(--primary);background:var(--bg-primary);padding:var(--sp-2);border-radius:var(--radius)">
                          <strong>修改建议：</strong>${clause.suggestedClause}
                        </div>
                      ` : ''}
                      ${clause.legalBasis ? `
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);margin-top:var(--sp-2)">
                          法律依据：${clause.legalBasis}
                        </div>
                      ` : ''}
                    </div>
                  `;
                }).join('')}
              </div>
            ` : `
              <div class="empty-state" style="padding:var(--sp-8)">
                ${Icons.shield(48)}
                <p style="color:var(--text-secondary)">暂无条款分析结果</p>
              </div>
            `}
          </div>
        </div>
      </div>`;
  }
};
