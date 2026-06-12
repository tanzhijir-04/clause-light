/* === Knowledge Base Page === */
const KnowledgePage = () => {
  const [tab, setTab] = React.useState('rules');
  const tabs = [
    { key: 'rules', label: '规则库' },
    { key: 'laws', label: '法规库' },
    { key: 'pending', label: '待审核' },
    { key: 'stats', label: '统计' },
  ];
  return (
    <div className="animate-in">
      <div className="content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>知识库管理</h1>
          <p>管理风险审查规则、法规条文和自动学习结果</p>
        </div>
        <button className="btn btn-primary"><IconPlus size={14} /> 新增规则</button>
      </div>
      <div className="content-body">
        <div className="tabs">
          {tabs.map(t => (
            <div key={t.key} className={`tab ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>{t.label}</div>
          ))}
        </div>

        {tab === 'rules' && (
          <div>
            <div style={{ display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
              <div className="input-with-icon" style={{ flex: 1 }}>
                <IconSearch size={16} />
                <input className="input" placeholder="搜索规则..." />
              </div>
              <select className="select">
                <option>所有类别</option>
                <option>通用</option>
                <option>租赁</option>
                <option>劳动</option>
                <option>装修</option>
                <option>外包</option>
              </select>
            </div>
            <div className="table-wrapper">
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
                <tbody>
                  {MOCK_RULES.map(r => (
                    <tr key={r.id}>
                      <td style={{ maxWidth: 400, whiteSpace: 'normal', fontWeight: 500 }}>{r.text}</td>
                      <td><span className="risk-badge" style={{ background: 'var(--accent-subtle)', color: 'var(--accent)', border: '1px solid var(--accent)' }}>{r.category}</span></td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
                          <div className="progress-bar" style={{ width: 60 }}>
                            <div className="progress-bar-fill accent" style={{ width: `${r.confidence * 100}%` }}></div>
                          </div>
                          <span className="table-cell-secondary">{(r.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="table-cell-secondary">
                        {r.source === 'manual' ? '手动' : r.source === 'auto_learned' ? '自动学习' : '用户反馈'}
                      </td>
                      <td className="table-cell-secondary">{r.usageCount}</td>
                      <td><div className={`toggle-track ${r.active ? 'on' : ''}`} style={{ width: 28, height: 16 }}><div className="toggle-thumb" style={{ width: 12, height: 12 }}></div></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === 'laws' && (
          <div>
            <div className="grid-2">
              <div className="card">
                <div className="card-header"><h3>中华人民共和国民法典</h3><span className="table-cell-secondary">42 条</span></div>
                <div className="card-body">
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--sp-3)' }}>合同编相关条文，涵盖合同订立、效力、履行、违约责任等</div>
                  <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                    <span className="risk-badge green" style={{ border: '1px solid var(--border-default)' }}>合同订立</span>
                    <span className="risk-badge yellow" style={{ border: '1px solid var(--border-default)' }}>违约责任</span>
                    <span className="risk-badge" style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)' }}>+5</span>
                  </div>
                </div>
              </div>
              <div className="card">
                <div className="card-header"><h3>中华人民共和国劳动合同法</h3><span className="table-cell-secondary">28 条</span></div>
                <div className="card-body">
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--sp-3)' }}>劳动合同订立、解除、竞业限制、加班、经济补偿等</div>
                  <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                    <span className="risk-badge red" style={{ border: '1px solid var(--border-default)' }}>竞业限制</span>
                    <span className="risk-badge yellow" style={{ border: '1px solid var(--border-default)' }}>加班条款</span>
                    <span className="risk-badge" style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)' }}>+3</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'pending' && (
          <div>
            <div className="card">
              <div className="card-header"><h3>待审核规则</h3><span className="table-cell-secondary">2 条待审核</span></div>
              <div className="card-body" style={{ padding: 0 }}>
                <table>
                  <thead><tr><th>规则内容</th><th>来源</th><th>置信度</th><th>操作</th></tr></thead>
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 500 }}>管辖法院约定为对方所在地法院的条款应标记为中风险</td>
                      <td className="table-cell-secondary">自动学习</td>
                      <td className="table-cell-secondary">78%</td>
                      <td><div style={{ display: 'flex', gap: 'var(--sp-2)' }}><button className="btn btn-sm btn-primary"><IconCheck size={12} /> 通过</button><button className="btn btn-sm btn-ghost"><IconX size={12} /> 拒绝</button></div></td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>装修合同未约定验收标准的应标记为中风险</td>
                      <td className="table-cell-secondary">用户反馈</td>
                      <td className="table-cell-secondary">85%</td>
                      <td><div style={{ display: 'flex', gap: 'var(--sp-2)' }}><button className="btn btn-sm btn-primary"><IconCheck size={12} /> 通过</button><button className="btn btn-sm btn-ghost"><IconX size={12} /> 拒绝</button></div></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {tab === 'stats' && (
          <div>
            <div className="stats-grid" style={{ marginBottom: 'var(--sp-6)' }}>
              <StatCard label="规则总数" value="8" icon={IconBook} />
              <StatCard label="法规条文" value="70" icon={IconDatabase} />
              <StatCard label="平均置信度" value="88%" icon={IconZap} />
              <StatCard label="待审核" value="2" icon={IconClock} />
            </div>
            <div className="card">
              <div className="card-header"><h3>规则使用频率</h3></div>
              <div className="card-body">
                {MOCK_RULES.slice(0, 5).map(r => (
                  <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-3)' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', width: 180, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.text}</span>
                    <div className="progress-bar" style={{ flex: 1 }}>
                      <div className="progress-bar-fill accent" style={{ width: `${(r.usageCount / 45) * 100}%` }}></div>
                    </div>
                    <span className="table-cell-secondary" style={{ width: 30, textAlign: 'right' }}>{r.usageCount}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};