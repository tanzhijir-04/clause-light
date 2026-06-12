/* === Sync Page === */
const SyncPage = () => (
  <div className="animate-in">
    <div className="content-header">
      <h1>同步管理</h1>
      <p>配置云同步服务，实现多设备数据同步</p>
    </div>
    <div className="content-body">
      <div className="grid-3" style={{ marginBottom: 'var(--sp-8)' }}>
        <div className="conn-card">
          <div className="conn-card-icon" style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}><IconCloud size={20} /></div>
          <div className="conn-card-info">
            <div className="conn-card-title">WebDAV</div>
            <div className="conn-card-desc">坚果云 / NextCloud</div>
          </div>
          <div className="toggle-track on"><div className="toggle-thumb"></div></div>
        </div>
        <div className="conn-card">
          <div className="conn-card-icon" style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}><IconGitBranch size={20} /></div>
          <div className="conn-card-info">
            <div className="conn-card-title">Git</div>
            <div className="conn-card-desc">Git 仓库同步</div>
          </div>
          <div className="toggle-track"><div className="toggle-thumb"></div></div>
        </div>
        <div className="conn-card">
          <div className="conn-card-icon" style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}><IconServer size={20} /></div>
          <div className="conn-card-info">
            <div className="conn-card-title">S3</div>
            <div className="conn-card-desc">MinIO / OSS / COS</div>
          </div>
          <div className="toggle-track"><div className="toggle-thumb"></div></div>
        </div>
      </div>

      <div className="detail-layout">
        <div>
          <div className="section">
            <div className="section-title">WebDAV 配置</div>
            <div className="config-card">
              <div className="form-group">
                <label className="form-label">服务器地址</label>
                <input className="input" defaultValue="https://dav.jianguoyun.com/dav/" />
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">用户名</label>
                  <input className="input" defaultValue="user@example.com" />
                </div>
                <div className="form-group">
                  <label className="form-label">应用密码</label>
                  <input className="input" type="password" defaultValue="••••••••" />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">远程路径</label>
                <input className="input" defaultValue="/合同红绿灯/" />
              </div>
              <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-4)' }}>
                <button className="btn btn-primary"><IconCheck size={14} /> 保存配置</button>
                <button className="btn btn-secondary"><IconRefresh size={14} /> 测试连接</button>
              </div>
            </div>
          </div>
        </div>

        <div>
          <div className="section">
            <div className="section-title">同步历史</div>
            <div className="card">
              <div className="card-body" style={{ padding: 'var(--sp-3) var(--sp-4)' }}>
                {MOCK_SYNC_LOG.map(log => (
                  <div key={log.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', padding: 'var(--sp-2) 0', borderBottom: log.id !== '4' ? '1px solid var(--border-subtle)' : 'none' }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: log.status === 'success' ? 'var(--risk-green)' : 'var(--risk-red)', flexShrink: 0 }}></div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>{log.type} {log.direction === 'push' ? '上传' : '下载'}</div>
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{log.details}</div>
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>{log.time}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="section">
            <div className="section-title">手动同步</div>
            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button className="btn btn-primary" style={{ flex: 1 }}><IconUpload size={14} /> 上传到云端</button>
              <button className="btn btn-secondary" style={{ flex: 1 }}><IconDownload size={14} /> 从云端下载</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);