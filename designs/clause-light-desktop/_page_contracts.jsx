/* === Contracts Page === */
const ContractsPage = () => (
  <div className="animate-in">
    <div className="content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <h1>合同管理</h1>
        <p>查看和管理所有已分析的合同</p>
      </div>
      <button className="btn btn-primary"><IconUpload size={14} /> 上传合同</button>
    </div>
    <div className="content-body">
      <div style={{ display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-6)' }}>
        <div className="input-with-icon" style={{ flex: 1 }}>
          <IconSearch size={16} />
          <input className="input" placeholder="搜索合同名称..." />
        </div>
        <select className="select">
          <option>所有类型</option>
          <option>租赁合同</option>
          <option>劳动合同</option>
          <option>装修合同</option>
          <option>外包合同</option>
          <option>借款合同</option>
        </select>
        <select className="select">
          <option>所有风险</option>
          <option>高风险</option>
          <option>中风险</option>
          <option>低风险</option>
        </select>
      </div>
      <div className="table-wrapper">
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
          <tbody>
            {MOCK_CONTRACTS.map(c => (
              <tr key={c.id} style={{ cursor: 'pointer' }}>
                <td style={{ fontWeight: 500 }}>{c.title}</td>
                <td className="table-cell-secondary">{c.type}</td>
                <td><RiskBadge level={c.riskLevel} /></td>
                <td><span className={c.score >= 70 ? 'score-green' : c.score >= 50 ? 'score-yellow' : 'score-red'} style={{ fontWeight: 600, fontSize: 'var(--text-md)' }}>{c.score}</span></td>
                <td style={{ minWidth: 120 }}><RiskDistBar red={c.redCount} yellow={c.yellowCount} green={c.greenCount} /></td>
                <td className="table-cell-secondary">{c.model}</td>
                <td className="table-cell-secondary">{c.createdAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </div>
);