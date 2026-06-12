/* === Settings Page === */
const SettingsPage = () => (
  <div className="animate-in">
    <div className="content-header">
      <h1>设置</h1>
      <p>LLM 配置、数据管理、客户端连接</p>
    </div>
    <div className="content-body">
      <div className="section">
        <div className="section-title">LLM 配置</div>
        <div className="config-card" style={{ marginBottom: 'var(--sp-4)' }}>
          <div className="config-card-header">
            <div className="config-card-title">远程 API</div>
            <div className="toggle-track on"><div className="toggle-thumb"></div></div>
          </div>
          <div className="config-card-desc">使用 OpenAI 兼容格式的云端 API（DeepSeek / OpenAI / 通义千问等）</div>
          <div className="form-group">
            <label className="form-label">提供商</label>
            <select className="select" style={{ width: '100%' }}>
              <option>DeepSeek</option>
              <option>OpenAI</option>
              <option>通义千问</option>
              <option>自定义</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">API Base URL</label>
            <input className="input" defaultValue="https://api.deepseek.com/v1" />
          </div>
          <div className="form-group">
            <label className="form-label">API Key</label>
            <input className="input" type="password" defaultValue="sk-••••••••••••••••" />
            <div className="form-hint">API Key 仅存储在本地，不会上传到任何服务器</div>
          </div>
          <div className="grid-3">
            <div className="form-group">
              <label className="form-label">分类模型</label>
              <input className="input" defaultValue="deepseek-chat" />
            </div>
            <div className="form-group">
              <label className="form-label">分析模型</label>
              <input className="input" defaultValue="deepseek-chat" />
            </div>
            <div className="form-group">
              <label className="form-label">解释模型</label>
              <input className="input" defaultValue="deepseek-chat" />
            </div>
          </div>
        </div>

        <div className="config-card">
          <div className="config-card-header">
            <div className="config-card-title">本地模型（Ollama）</div>
            <div className="toggle-track"><div className="toggle-thumb"></div></div>
          </div>
          <div className="config-card-desc">使用 Ollama 运行本地大模型，无需网络，数据完全不出本机</div>
          <div className="form-group">
            <label className="form-label">Ollama 地址</label>
            <input className="input" defaultValue="http://localhost:11434" />
          </div>
          <div className="grid-3">
            <div className="form-group">
              <label className="form-label">分类模型</label>
              <input className="input" defaultValue="qwen2.5:7b" />
            </div>
            <div className="form-group">
              <label className="form-label">分析模型</label>
              <input className="input" defaultValue="qwen2.5:32b" />
            </div>
            <div className="form-group">
              <label className="form-label">解释模型</label>
              <input className="input" defaultValue="qwen2.5:7b" />
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">客户端连接</div>
        <div className="card">
          <div className="card-body" style={{ padding: 0 }}>
            <table>
              <thead><tr><th>设备</th><th>类型</th><th>状态</th><th>IP 地址</th><th>最近活跃</th></tr></thead>
              <tbody>
                {MOCK_DEVICES.map(d => (
                  <tr key={d.id}>
                    <td style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
                      <IconSmartphone size={16} style={{ opacity: 0.5 }} /> {d.name}
                    </td>
                    <td className="table-cell-secondary">{d.type === 'mobile' ? '手机' : '平板'}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-1)' }}>
                        <div className={`status-dot ${d.status === 'online' ? '' : 'offline'}`}></div>
                        <span style={{ fontSize: 'var(--text-xs)', color: d.status === 'online' ? 'var(--risk-green)' : 'var(--text-tertiary)' }}>{d.status === 'online' ? '在线' : '离线'}</span>
                      </div>
                    </td>
                    <td className="table-cell-secondary" style={{ fontFamily: 'var(--font-mono)' }}>{d.ip}</td>
                    <td className="table-cell-secondary">{d.lastSeen}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">数据管理</div>
        <div className="config-card">
          <div style={{ display: 'flex', gap: 'var(--sp-3)', flexWrap: 'wrap' }}>
            <button className="btn btn-secondary"><IconDownload size={14} /> 导出全部数据</button>
            <button className="btn btn-secondary"><IconDatabase size={14} /> 备份数据库</button>
            <button className="btn btn-secondary"><IconRefresh size={14} /> 重建索引</button>
            <button className="btn btn-ghost" style={{ color: 'var(--risk-red)' }}><IconTrash size={14} /> 清除所有数据</button>
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">关于</div>
        <div className="config-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
            <div className="sidebar-logo" style={{ width: 36, height: 36, fontSize: 'var(--text-md)' }}>CL</div>
            <div>
              <div style={{ fontWeight: 600 }}>ClauseLight（合同红绿灯）</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>v1.0.0 · MIT License · 开源项目</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);