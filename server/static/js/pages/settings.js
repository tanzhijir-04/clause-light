/**
 * 设置页面
 */
const SettingsPage = {
  /** 开关状态 */
  _remoteEnabled: false,
  _localEnabled: false,

  /** 自动保存防抖定时器 */
  _saveTimer: null,

  /** 提供商 → 默认 Base URL 映射 */
  _providerUrls: {
    deepseek: 'https://api.deepseek.com/v1',
    openai: 'https://api.openai.com/v1',
    qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    custom: '',
  },

  async render() {
    const llmConfig = await API.settings.llm();

    // 获取连接信息
    let connInfo = { host: '0.0.0.0', port: 8080, ws_url: 'ws://0.0.0.0:8080/ws/client' };
    let connHealth = { status: 'ok', active_connections: 0, version: '0.1.0', uptime: 0 };
    let connDevices = { devices: [], total: 0, online: 0 };
    try {
      connInfo = await API.connection.info();
      connHealth = await API.connection.health();
      connDevices = await API.connection.devices();
    } catch (e) {
      console.warn('获取连接信息失败:', e);
    }

    // 设备表格
    let deviceRows = '';
    connDevices.devices.forEach(d => {
      const statusColor = d.status === 'online' ? 'var(--risk-green)' : 'var(--text-tertiary)';
      const statusText = d.status === 'online' ? '在线' : '离线';
      const dotClass = d.status === 'online' ? '' : ' offline';
      const connectedTime = d.connectedAt ? new Date(d.connectedAt).toLocaleString('zh-CN') : '-';
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
        <td class="table-cell-secondary">${connectedTime}</td>
      </tr>`;
    });

    if (!deviceRows) {
      deviceRows = `<tr><td colspan="5" style="text-align:center;color:var(--text-tertiary);padding:var(--sp-8) 0">
        暂无设备连接，请使用手机扫描右侧二维码
      </td></tr>`;
    }

    // 远程 API 配置
    const remote = llmConfig.remote || {};
    const remoteModels = remote.models || {};
    SettingsPage._remoteEnabled = remote.enabled !== false;

    // 本地模型配置
    const local = llmConfig.local || {};
    const localModels = local.models || {};
    SettingsPage._localEnabled = local.enabled === true;

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
            ${Components.Toggle('llm-remote', SettingsPage._remoteEnabled)}
          </div>
          <div class="config-card-desc">使用 OpenAI 兼容格式的云端 API（DeepSeek / OpenAI / 通义千问等）</div>
          <div class="form-group">
            <label class="form-label">提供商</label>
            <select id="llm-provider" class="select" style="width:100%">
              <option value="deepseek" ${remote.provider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
              <option value="openai" ${remote.provider === 'openai' ? 'selected' : ''}>OpenAI</option>
              <option value="qwen" ${remote.provider === 'qwen' ? 'selected' : ''}>通义千问</option>
              <option value="custom" ${remote.provider === 'custom' ? 'selected' : ''}>自定义</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">API Base URL</label>
            <input id="llm-baseUrl" class="input" value="${remote.baseUrl || 'https://api.deepseek.com/v1'}" />
          </div>
          <div class="form-group">
            <label class="form-label">API Key</label>
            <input id="llm-apiKey" class="input" type="password" value="${remote.apiKey || ''}" placeholder="sk-..." />
            <div class="form-hint">API Key 仅存储在本地，不会上传到任何服务器</div>
          </div>
          <div class="grid-3">
            <div class="form-group">
              <label class="form-label">分类模型</label>
              <input id="llm-classify" class="input" value="${remoteModels.classify || 'deepseek-chat'}" />
            </div>
            <div class="form-group">
              <label class="form-label">分析模型</label>
              <input id="llm-analyze" class="input" value="${remoteModels.analyze || 'deepseek-chat'}" />
            </div>
            <div class="form-group">
              <label class="form-label">解释模型</label>
              <input id="llm-explain" class="input" value="${remoteModels.explain || 'deepseek-chat'}" />
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:var(--sp-3);margin-top:var(--sp-4);padding-top:var(--sp-4);border-top:1px solid var(--border-default)">
            <button class="btn btn-secondary btn-sm" onclick="SettingsPage.testRemote()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
              测试连接
            </button>
            <span id="remote-test-result" style="font-size:var(--text-xs)"></span>
          </div>
        </div>

        <!-- 本地模型 -->
        <div class="config-card" style="margin-bottom:var(--sp-4)">
          <div class="config-card-header">
            <div class="config-card-title">本地模型（Ollama）</div>
            ${Components.Toggle('llm-local', SettingsPage._localEnabled)}
          </div>
          <div class="config-card-desc">使用 Ollama 运行本地大模型，无需网络，数据完全不出本机</div>
          <div class="form-group">
            <label class="form-label">Ollama 地址</label>
            <input id="llm-local-endpoint" class="input" value="${local.endpoint || 'http://localhost:11434'}" />
          </div>
          <div class="grid-3">
            <div class="form-group">
              <label class="form-label">分类模型</label>
              <input id="llm-local-classify" class="input" value="${localModels.classify || 'qwen2.5:7b'}" />
            </div>
            <div class="form-group">
              <label class="form-label">分析模型</label>
              <input id="llm-local-analyze" class="input" value="${localModels.analyze || 'qwen2.5:32b'}" />
            </div>
            <div class="form-group">
              <label class="form-label">解释模型</label>
              <input id="llm-local-explain" class="input" value="${localModels.explain || 'qwen2.5:7b'}" />
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:var(--sp-3);margin-top:var(--sp-4);padding-top:var(--sp-4);border-top:1px solid var(--border-default)">
            <button class="btn btn-secondary btn-sm" onclick="SettingsPage.testLocal()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
              测试连接
            </button>
            <span id="local-test-result" style="font-size:var(--text-xs)"></span>
          </div>
        </div>

        <div style="display:flex;align-items:center;gap:var(--sp-3)">
          <button class="btn btn-primary" onclick="SettingsPage.saveLLM()">保存配置</button>
          <span id="llm-save-status" style="font-size:var(--text-xs);color:var(--text-tertiary)"></span>
        </div>
      </div>

      <div class="section">
        <div class="section-title">客户端连接</div>
        <div class="card" style="margin-bottom:var(--sp-4)">
          <div class="card-body">
            <div style="display:flex;gap:var(--sp-8);align-items:flex-start;flex-wrap:wrap">
              <!-- 左侧：连接信息 -->
              <div style="flex:1;min-width:240px">
                <div style="margin-bottom:var(--sp-4)">
                  <div class="form-label" style="margin-bottom:var(--sp-2)">WebSocket 地址</div>
                  <div style="display:flex;align-items:center;gap:var(--sp-2)">
                    <code style="flex:1;padding:var(--sp-2) var(--sp-3);background:var(--bg-muted);border-radius:var(--radius-md);font-family:var(--font-mono);font-size:var(--text-sm);word-break:break-all">${connInfo.ws_url}</code>
                    <button class="btn btn-secondary btn-sm" onclick="SettingsPage.copyWsUrl()" title="复制地址">
                      ${Icons.copy(14)}
                    </button>
                  </div>
                </div>
                <div style="display:flex;gap:var(--sp-6);margin-bottom:var(--sp-4)">
                  <div>
                    <div class="form-label" style="margin-bottom:var(--sp-1)">服务状态</div>
                    <div style="display:flex;align-items:center;gap:var(--sp-2)">
                      <div class="status-dot" style="background:var(--risk-green)"></div>
                      <span style="font-size:var(--text-sm);color:var(--risk-green-text);font-weight:500">正常运行</span>
                    </div>
                  </div>
                  <div>
                    <div class="form-label" style="margin-bottom:var(--sp-1)">活跃连接</div>
                    <span style="font-size:var(--text-sm);font-weight:600">${connHealth.active_connections}</span>
                  </div>
                  <div>
                    <div class="form-label" style="margin-bottom:var(--sp-1)">运行时间</div>
                    <span style="font-size:var(--text-sm)">${SettingsPage._formatUptime(connHealth.uptime)}</span>
                  </div>
                </div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);line-height:1.6">
                  手机端扫描右侧二维码即可自动连接到本机。确保手机和电脑在同一局域网内。
                </div>
              </div>
              <!-- 右侧：二维码 -->
              <div style="text-align:center;flex-shrink:0">
                <div id="qr-code-container" style="width:200px;height:200px;border:1px solid var(--border-default);border-radius:var(--radius-lg);display:flex;align-items:center;justify-content:center;background:var(--bg-surface);overflow:hidden">
                  <img id="qr-code-img" src="${API.connection.qrUrl()}" alt="扫码连接" style="width:100%;height:100%;object-fit:contain" onerror="this.parentElement.innerHTML='<div style=\\'color:var(--text-tertiary);font-size:var(--text-xs\\'>二维码加载失败</div>'" />
                </div>
                <button class="btn btn-secondary btn-sm" style="margin-top:var(--sp-3)" onclick="SettingsPage.refreshQr()">
                  ${Icons.refresh(14)} 刷新二维码
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 已连接设备 -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">已连接设备</div>
            <span style="font-size:var(--text-xs);color:var(--text-tertiary)">${connDevices.online} / ${connDevices.total} 在线</span>
          </div>
          <div class="card-body" style="padding:0">
            <table>
              <thead>
                <tr>
                  <th>设备</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>IP 地址</th>
                  <th>连接时间</th>
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
            <button class="btn btn-secondary" onclick="SettingsPage.exportData()">${Icons.download(14)} 导出全部数据</button>
            <button class="btn btn-secondary" onclick="SettingsPage.backupDb()">${Icons.database(14)} 备份数据库</button>
            <button class="btn btn-secondary" onclick="SettingsPage.rebuildIndex()">${Icons.refresh(14)} 重建索引</button>
            <button class="btn btn-danger" onclick="SettingsPage.clearData()">${Icons.trash(14)} 清除所有数据</button>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">关于</div>
        <div class="config-card">
          <div class="about-section">
            <div class="about-logo">
              <img src="/asset/合同红绿灯-app-icon--ios-android-.svg" alt="合同红绿灯" style="width:64px;height:64px;" />
            </div>
            <div class="about-info">
              <h3>合同红绿灯</h3>
              <p>v1.0.0 · MIT License · 开源项目</p>
            </div>
          </div>
        </div>
      </div>
      </div>`;
  },

  /** 初始化 Toggle 回调 + 自动保存事件（页面渲染后调用） */
  initToggles() {
    // Toggle 回调
    Components.onToggle('llm-remote', (on) => {
      SettingsPage._remoteEnabled = on;
      SettingsPage._debouncedSave();
    });
    Components.onToggle('llm-local', (on) => {
      SettingsPage._localEnabled = on;
      SettingsPage._debouncedSave();
    });

    // 给所有 LLM 表单字段绑定自动保存
    const fields = [
      'llm-provider', 'llm-baseUrl', 'llm-apiKey',
      'llm-classify', 'llm-analyze', 'llm-explain',
      'llm-local-endpoint', 'llm-local-classify', 'llm-local-analyze', 'llm-local-explain',
    ];
    fields.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => SettingsPage._debouncedSave());
        el.addEventListener('change', () => SettingsPage._debouncedSave());
      }
    });

    // 提供商下拉 → 自动填充 Base URL
    const providerEl = document.getElementById('llm-provider');
    if (providerEl) {
      providerEl.addEventListener('change', (e) => {
        const url = SettingsPage._providerUrls[e.target.value];
        if (url !== undefined) {
          const baseUrlEl = document.getElementById('llm-baseUrl');
          // 只在用户没手动改过时自动填充，或者当前值是某个已知 provider 的 url
          if (baseUrlEl && Object.values(SettingsPage._providerUrls).includes(baseUrlEl.value)) {
            baseUrlEl.value = url;
          }
        }
      });
    }
  },

  /** 防抖自动保存（500ms） */
  _debouncedSave() {
    if (SettingsPage._saveTimer) clearTimeout(SettingsPage._saveTimer);
    SettingsPage._saveTimer = setTimeout(() => SettingsPage.saveLLM(true), 500);
  },

  /** 保存 LLM 配置 */
  async saveLLM(silent = false) {
    const data = {
      remote: {
        enabled: SettingsPage._remoteEnabled,
        provider: document.getElementById('llm-provider')?.value || 'deepseek',
        baseUrl: document.getElementById('llm-baseUrl')?.value || '',
        apiKey: document.getElementById('llm-apiKey')?.value || '',
        models: {
          classify: document.getElementById('llm-classify')?.value || '',
          analyze: document.getElementById('llm-analyze')?.value || '',
          explain: document.getElementById('llm-explain')?.value || '',
        },
      },
      local: {
        enabled: SettingsPage._localEnabled,
        endpoint: document.getElementById('llm-local-endpoint')?.value || '',
        models: {
          classify: document.getElementById('llm-local-classify')?.value || '',
          analyze: document.getElementById('llm-local-analyze')?.value || '',
          explain: document.getElementById('llm-local-explain')?.value || '',
        },
      },
    };

    try {
      await API.settings.updateLLM(data);
      if (!silent) {
        Components.toast('配置已保存', 'success');
      } else {
        const statusEl = document.getElementById('llm-save-status');
        if (statusEl) {
          statusEl.textContent = '已自动保存';
          statusEl.style.color = 'var(--risk-green)';
          setTimeout(() => { statusEl.textContent = ''; }, 2000);
        }
      }
    } catch (e) {
      if (!silent) {
        Components.toast('保存失败: ' + e.message, 'error');
      }
    }
  },

  /** 测试远程 API 连接 */
  async testRemote() {
    const btn = document.querySelector('[onclick="SettingsPage.testRemote()"]');
    const resultEl = document.getElementById('remote-test-result');
    if (btn) btn.disabled = true;
    if (resultEl) {
      resultEl.textContent = '测试中...';
      resultEl.style.color = 'var(--text-tertiary)';
    }

    try {
      const res = await API.settings.testLLM();
      if (res.success) {
        const latency = res.latency_ms;
        let color = 'var(--risk-green)';
        let label = `${latency}ms`;
        if (latency > 3000) {
          color = 'var(--risk-red)';
          label = `${latency}ms（慢）`;
        } else if (latency > 1000) {
          color = 'var(--risk-yellow)';
          label = `${latency}ms（较慢）`;
        }
        if (resultEl) {
          resultEl.innerHTML = `✓ 连接成功 — ${res.model} — <span style="color:${color}">${label}</span>`;
        }
      } else {
        if (resultEl) {
          resultEl.innerHTML = `<span style="color:var(--risk-red)">✗ ${res.error || '连接失败'}</span>`;
        }
      }
    } catch (e) {
      if (resultEl) {
        resultEl.innerHTML = `<span style="color:var(--risk-red)">✗ ${e.message}</span>`;
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  /** 测试本地 Ollama 连接 */
  async testLocal() {
    const btn = document.querySelector('[onclick="SettingsPage.testLocal()"]');
    const resultEl = document.getElementById('local-test-result');
    if (btn) btn.disabled = true;
    if (resultEl) {
      resultEl.textContent = '测试中...';
      resultEl.style.color = 'var(--text-tertiary)';
    }

    try {
      const res = await API.settings.testLLMLocal();
      if (res.success) {
        const latency = res.latency_ms;
        let color = 'var(--risk-green)';
        let label = `${latency}ms`;
        if (latency > 3000) {
          color = 'var(--risk-red)';
          label = `${latency}ms（慢）`;
        } else if (latency > 1000) {
          color = 'var(--risk-yellow)';
          label = `${latency}ms（较慢）`;
        }
        const count = res.models ? res.models.length : 0;
        const modelInfo = count > 0 ? ` — 已安装 ${count} 个模型` : '';
        if (resultEl) {
          resultEl.innerHTML = `✓ 连接成功${modelInfo} — <span style="color:${color}">${label}</span>`;
          resultEl.style.color = '';
        }
      } else {
        if (resultEl) {
          resultEl.innerHTML = `<span style="color:var(--risk-red)">✗ ${res.error || '连接失败'}</span>`;
        }
      }
    } catch (e) {
      if (resultEl) {
        resultEl.innerHTML = `<span style="color:var(--risk-red)">✗ ${e.message}</span>`;
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  exportData() {
    Components.toast('导出功能将在后端 API 实现后可用', 'info');
  },

  backupDb() {
    Components.toast('备份功能将在后端 API 实现后可用', 'info');
  },

  rebuildIndex() {
    Components.toast('重建索引功能将在后端 API 实现后可用', 'info');
  },

  clearData() {
    if (confirm('确定要清除所有数据吗？此操作不可恢复！')) {
      Components.toast('清除功能将在后端 API 实现后可用', 'info');
    }
  },

  /** 复制 WebSocket 地址到剪贴板 */
  async copyWsUrl() {
    try {
      const info = await API.connection.info();
      await navigator.clipboard.writeText(info.ws_url);
      Components.toast('已复制 WebSocket 地址', 'success');
    } catch {
      Components.toast('复制失败', 'error');
    }
  },

  /** 刷新二维码 */
  refreshQr() {
    const img = document.getElementById('qr-code-img');
    if (img) {
      img.src = API.connection.qrUrl();
    }
  },

  /** 格式化运行时间 */
  _formatUptime(seconds) {
    if (!seconds || seconds < 0) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}小时${m}分钟`;
    if (m > 0) return `${m}分钟`;
    return `${seconds}秒`;
  },
};
