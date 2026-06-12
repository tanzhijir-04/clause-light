/* === Dashboard Page === */
const DashboardPage = () => (
  <div className="animate-in">
    <div className="content-header">
      <h1>仪表盘</h1>
      <p>合同风险审查概览</p>
    </div>
    <div className="content-body">
      <div className="stats-grid" style={{ marginBottom: 'var(--sp-6)' }}>
        <StatCard label="合同总数" value="6" change="本月 +2" changeType="up" icon={IconFileText} />
        <StatCard label="平均风险分" value="59" change="较上月 +3" changeType="up" icon={IconBarChart} />
        <StatCard label="知识库规则" value="8" change="自动学习 +1" changeType="up" icon={IconBook} />
        <StatCard label="连接设备" value="1" change="iPhone 15 Pro 在线" changeType="up" icon={IconSmartphone} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--sp-6)' }}>
        <div className="card">
          <div className="card-header">
            <h3>最近分析</h3>
            <button className="btn btn-ghost btn-sm">查看全部</button>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
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
              <tbody>
                {MOCK_CONTRACTS.map(c => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 500 }}>{c.title}</td>
                    <td className="table-cell-secondary">{c.type}</td>
                    <td><span className={c.score >= 70 ? 'score-green' : c.score >= 50 ? 'score-yellow' : 'score-red'} style={{ fontWeight: 600 }}>{c.score}</span></td>
                    <td style={{ minWidth: 120 }}><RiskDistBar red={c.redCount} yellow={c.yellowCount} green={c.greenCount} /></td>
                    <td className="table-cell-secondary">{c.createdAt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
          <div className="card">
            <div className="card-header">
              <h3>风险分布</h3>
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', gap: 'var(--sp-6)', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--risk-red)' }}>18</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>高风险</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--risk-yellow)' }}>16</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>中风险</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--risk-green)' }}>30</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>低风险</div>
                </div>
              </div>
              <RiskDistBar red={18} yellow={16} green={30} />
            </div>
          </div>

          <div className="upload-zone">
            <IconUpload size={36} />
            <div className="upload-zone-title">快速上传合同</div>
            <div className="upload-zone-hint">拖放文件或点击选择</div>
            <button className="btn btn-primary" style={{ marginTop: 'var(--sp-2)' }}>
              <IconUpload size={14} /> 选择文件
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
);