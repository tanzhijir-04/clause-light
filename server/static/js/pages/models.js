/**
 * 模型管理页面 — OCR 模型状态、下载、删除
 */
const ModelsPage = {
  async render() {
    const status = await API.models.status();
    if (!status) {
      return `<div class="empty-state">无法获取模型状态，请检查后端是否运行</div>`;
    }

    // 模型表格
    let modelRows = '';
    (status.models || []).forEach(m => {
      const statusLabel = m.installed
        ? '<span style="color:var(--risk-green)">✓ 已安装</span>'
        : '<span style="color:var(--text-tertiary)">✗ 未安装</span>';
      const sizeText = m.installed
        ? `${m.installed_size_mb} MB`
        : `${m.total_size_mb} MB`;
      const actionBtn = m.installed
        ? `<button class="btn btn-sm btn-danger" onclick="ModelsPage.deleteModel('${m.type}')">删除</button>`
        : `<button class="btn btn-sm btn-primary" onclick="ModelsPage.downloadModel('${m.type}')">下载</button>`;

      modelRows += `<tr>
        <td style="font-weight:500">${m.description}</td>
        <td>${statusLabel}</td>
        <td style="font-family:var(--font-mono);font-size:var(--text-xs)">${sizeText}</td>
        <td>${actionBtn}</td>
      </tr>`;
    });

    // 需要下载的总大小
    const pendingSize = status.models
      ? status.models.filter(m => !m.installed).reduce((s, m) => s + m.total_size_mb, 0)
      : 0;

    return `
      <div class="content-header animate-in">
        <div class="content-title">模型管理</div>
        <div class="content-subtitle">OCR 模型状态、下载、配置</div>
      </div>
      <div class="content-body animate-in">

      <div class="section">
        <div class="section-title">OCR 模型状态</div>

        <table class="table" style="margin-bottom:var(--sp-4)">
          <thead>
            <tr>
              <th>模型</th>
              <th>状态</th>
              <th>大小</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${modelRows}
          </tbody>
        </table>

        <div id="models-progress" style="display:none;margin-bottom:var(--sp-4)">
          <div style="display:flex;justify-content:space-between;margin-bottom:var(--sp-1)">
            <span id="models-progress-text" style="font-size:var(--text-xs);color:var(--text-secondary)">准备中...</span>
            <span id="models-progress-pct" style="font-size:var(--text-xs);font-family:var(--font-mono)">0%</span>
          </div>
          <div class="progress-bar">
            <div id="models-progress-fill" class="progress-bar-fill accent" style="width:0%"></div>
          </div>
        </div>

        ${pendingSize > 0 ? `
          <button class="btn btn-primary" id="btn-download-all" onclick="ModelsPage.downloadAll()">
            一键下载全部模型
          </button>
          <span style="font-size:var(--text-xs);color:var(--text-tertiary);margin-left:var(--sp-2)">
            共需下载: ~${pendingSize.toFixed(1)} MB
          </span>
        ` : `
          <span style="font-size:var(--text-xs);color:var(--risk-green)">所有模型已安装</span>
        `}
      </div>

      <div class="section">
        <div class="section-title">模型存储路径</div>
        <div style="font-family:var(--font-mono);font-size:var(--text-sm);color:var(--text-secondary);padding:var(--sp-3);background:var(--bg-muted);border-radius:var(--radius-sm)">
          ${status.model_dir}
        </div>
        <div style="font-size:var(--text-xs);color:var(--text-tertiary);margin-top:var(--sp-1)">
          修改路径请在 .env 文件中设置 OCR_MODEL_DIR，修改后需重启生效
        </div>
      </div>

      <div class="section">
        <div class="section-title">LLM 配置状态</div>
        ${await ModelsPage._renderLLMStatus()}
      </div>

      </div>`;
  },

  async _renderLLMStatus() {
    try {
      const llm = await API.settings.llm();
      const remoteOk = llm.remote?.enabled !== false && llm.remote?.apiKey;
      const localOk = llm.local?.enabled === true;
      return `
        <div style="display:flex;gap:var(--sp-6);font-size:var(--text-sm)">
          <div>
            <span style="color:var(--text-tertiary)">DeepSeek:</span>
            ${remoteOk
              ? ' <span style="color:var(--risk-green)">✓ 已配置</span>'
              : ' <span style="color:var(--text-tertiary)">✗ 未配置</span>'}
          </div>
          <div>
            <span style="color:var(--text-tertiary)">Ollama:</span>
            ${localOk
              ? ' <span style="color:var(--risk-green)">✓ 已启用</span>'
              : ' <span style="color:var(--text-tertiary)">✗ 未启用</span>'}
          </div>
        </div>`;
    } catch {
      return '<div style="font-size:var(--text-xs);color:var(--text-tertiary)">无法获取 LLM 配置</div>';
    }
  },

  /** 下载单个模型 */
  async downloadModel(modelType) {
    const progressEl = document.getElementById('models-progress');
    const textEl = document.getElementById('models-progress-text');
    const pctEl = document.getElementById('models-progress-pct');
    const fillEl = document.getElementById('models-progress-fill');

    progressEl.style.display = 'block';
    textEl.textContent = `正在下载 ${modelType}...`;
    pctEl.textContent = '0%';
    fillEl.style.width = '0%';

    try {
      const response = await fetch(`/api/models/download/${modelType}`, { method: 'POST' });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        const lines = text.split('\n').filter(l => l.startsWith('data: '));
        for (const line of lines) {
          const event = JSON.parse(line.slice(6));
          textEl.textContent = event.message || '';
          if (event.progress !== undefined) {
            const pct = Math.round(event.progress * 100);
            pctEl.textContent = `${pct}%`;
            fillEl.style.width = `${pct}%`;
          }
          if (event.status === 'done') {
            pctEl.textContent = '100%';
            fillEl.style.width = '100%';
            setTimeout(() => App.renderPage('models'), 1000);
          }
          if (event.status === 'error') {
            textEl.textContent = event.message;
            textEl.style.color = 'var(--risk-red)';
          }
        }
      }
    } catch (e) {
      textEl.textContent = `下载失败: ${e.message}`;
      textEl.style.color = 'var(--risk-red)';
    }
  },

  /** 下载全部模型 */
  async downloadAll() {
    const progressEl = document.getElementById('models-progress');
    const textEl = document.getElementById('models-progress-text');
    const pctEl = document.getElementById('models-progress-pct');
    const fillEl = document.getElementById('models-progress-fill');
    const btn = document.getElementById('btn-download-all');

    progressEl.style.display = 'block';
    if (btn) btn.disabled = true;
    textEl.textContent = '准备下载全部模型...';
    pctEl.textContent = '0%';
    fillEl.style.width = '0%';

    try {
      const response = await fetch('/api/models/download-all', { method: 'POST' });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        const lines = text.split('\n').filter(l => l.startsWith('data: '));
        for (const line of lines) {
          const event = JSON.parse(line.slice(6));
          textEl.textContent = event.message || '';
          if (event.progress !== undefined) {
            const pct = Math.round(event.progress * 100);
            pctEl.textContent = `${pct}%`;
            fillEl.style.width = `${pct}%`;
          }
          if (event.status === 'done') {
            pctEl.textContent = '100%';
            fillEl.style.width = '100%';
          }
          if (event.status === 'error') {
            textEl.textContent = event.message;
            textEl.style.color = 'var(--risk-red)';
          }
        }
      }
      // 刷新页面
      setTimeout(() => App.renderPage('models'), 1500);
    } catch (e) {
      textEl.textContent = `下载失败: ${e.message}`;
      textEl.style.color = 'var(--risk-red)';
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  /** 删除模型 */
  async deleteModel(modelType) {
    if (!confirm(`确定要删除模型 ${modelType} 吗？`)) return;

    try {
      const res = await fetch(`/api/models/${modelType}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        Components.toast(data.message, 'success');
        App.renderPage('models');
      } else {
        Components.toast(data.message, 'error');
      }
    } catch (e) {
      Components.toast(`删除失败: ${e.message}`, 'error');
    }
  },
};
