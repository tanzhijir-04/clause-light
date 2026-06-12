/**
 * 设置页面
 */
const SettingsPage = {
  async render() {
    const llmConfig = await API.settings.llm();
    const devices = await API.settings.devices();

    // 设备表格
    let deviceRows = '';
    devices.forEach(d => {
      const statusColor = d.status === 'online' ? 'var(--risk-green)' : 'var(--text-tertiary)';
      const statusText = d.status === 'online' ? '在线' : '离线';
      const dotClass = d.status === 'online' ? '' : ' offline';
      deviceRows += `<tr>
        <td>
          <div class="device-name-cell">
            ${Icons.smartphone(16)}
            <span style="font-weight:500">${d.name}</span>
          </div>
        </td>
        <td class="table-cell-secondary">${d.type === 'mobile' ? '手机' : '平板'}</td>
        <td>
          <div class="device-status">
            <div class="status-dot${dotClass}"></div>
            <span class="device-status-text" style="color:${statusColor}">${statusText}</span>
          </div>
        </td>
        <td class="table-cell-secondary" style="font-family:var(--font-mono)">${d.ip}</td>
        <td class="table-cell-secondary">${d.lastSeen}</td>
      </tr>`;
    });

    // 远程 API 配置
    const remoteEnabled = llmConfig.remote?.enabled !== false;
    const remote = llmConfig.remote || {};
    const remoteModels = remote.models || {};

    // 本地模型配置
    const localEnabled = llmConfig.local?.enabled === true;
    const local = llmConfig.local || {};
    const localModels = local.models || {};

    return `
      <div class="content-header animate-in">
        <div class="content-title">设置</div>
        <div class="content-subtitle">LLM 配置、数据管理、客户端连接</div>
      </div>
      <div class="content-body animate-in">

      <div class="section">
        <div class="section-title">LLM 配置</div>

        <!-- 远程 API -->
        <div class="config-card" style="margin-bottom:var(--sp-4)">
          <div class="config-card-header">
            <div class="config-card-title">远程 API</div>
            ${Components.Toggle('llm-remote', remoteEnabled)}
          </div>
          <div class="config-card-desc">使用 OpenAI 兼容格式的云端 API（DeepSeek / OpenAI / 通义千问等）</div>
          <div class="form-group">
            <label class="form-label">提供商</label>
            <select class="select" style="width:100%">
              <option ${remote.provider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
              <option ${remote.provider === 'openai' ? 'selected' : ''}>OpenAI</option>
              <option ${remote.provider === 'qwen' ? 'selected' : ''}>通义千问</option>
              <option>自定义</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">API Base URL</label>
            <input class="input" value="${remote.baseUrl || 'https://api.deepseek.com/v1'}" />
          </div>
          <div class="form-group">
            <label class="form-label">API Key</label>
            <input class="input" type="password" value="${remote.apiKey || ''}" placeholder="sk-..." />
            <div class="form-hint">API Key 仅存储在本地，不会上传到任何服务器</div>
          </div>
          <div class="grid-3">
            <div class="form-group">
              <label class="form-label">分类模型</label>
              <input class="input" value="${remoteModels.classify || 'deepseek-chat'}" />
            </div>
            <div class="form-group">
              <label class="form-label">分析模型</label>
              <input class="input" value="${remoteModels.analyze || 'deepseek-chat'}" />
            </div>
            <div class="form-group">
              <label class="form-label">解释模型</label>
              <input class="input" value="${remoteModels.explain || 'deepseek-chat'}" />
            </div>
          </div>
        </div>

        <!-- 本地模型 -->
        <div class="config-card">
          <div class="config-card-header">
            <div class="config-card-title">本地模型（Ollama）</div>
            ${Components.Toggle('llm-local', localEnabled)}
          </div>
          <div class="config-card-desc">使用 Ollama 运行本地大模型，无需网络，数据完全不出本机</div>
          <div class="form-group">
            <label class="form-label">Ollama 地址</label>
            <input class="input" value="${local.endpoint || 'http://localhost:11434'}" />
          </div>
          <div class="grid-3">
            <div class="form-group">
              <label class="form-label">分类模型</label>
              <input class="input" value="${localModels.classify || 'qwen2.5:7b'}" />
            </div>
            <div class="form-group">
              <label class="form-label">分析模型</label>
              <input class="input" value="${localModels.analyze || 'qwen2.5:32b'}" />
            </div>
            <div class="form-group">
              <label class="form-label">解释模型</label>
              <input class="input" value="${localModels.explain || 'qwen2.5:7b'}" />
            </div>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">客户端连接</div>
        <div class="card">
          <div class="card-body" style="padding:0">
            <table>
              <thead>
                <tr>
                  <th>设备</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>IP 地址</th>
                  <th>最近活跃</th>
                </tr>
              </thead>
              <tbody>${deviceRows}</tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">数据管理</div>
        <div class="config-card">
          <div class="data-actions">
            <button class="btn btn-secondary">${Icons.download(14)} 导出全部数据</button>
            <button class="btn btn-secondary">${Icons.database(14)} 备份数据库</button>
            <button class="btn btn-secondary">${Icons.refresh(14)} 重建索引</button>
            <button class="btn btn-danger">${Icons.trash(14)} 清除所有数据</button>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">关于</div>
        <div class="config-card">
          <div class="about-section">
            <div class="about-logo">CL</div>
            <div class="about-info">
              <h3>ClauseLight（合同红绿灯）</h3>
              <p>v1.0.0 · MIT License · 开源项目</p>
            </div>
          </div>
        </div>
      </div>
      </div>`;
  },
};
