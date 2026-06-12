/**
 * 同步管理页面
 */
const SyncPage = {
  _selectedService: 'webdav',
  _services: {
    webdav: { enabled: true, name: 'WebDAV', desc: '坚果云 / NextCloud', icon: 'cloud' },
    git: { enabled: false, name: 'Git', desc: 'Git 仓库同步', icon: 'gitBranch' },
    s3: { enabled: false, name: 'S3', desc: 'MinIO / OSS / COS', icon: 'server' },
  },

  async render() {
    const logs = await API.sync.log();

    // 连接卡片
    let connCardsHtml = '';
    Object.entries(this._services).forEach(([key, svc]) => {
      const isSelected = this._selectedService === key;
      const iconClass = svc.enabled ? 'active' : 'muted';
      connCardsHtml += `
        <div class="conn-card ${isSelected ? 'selected' : ''}" onclick="SyncPage.selectService('${key}')">
          <div class="conn-card-icon ${iconClass}">${Icons[svc.icon](20)}</div>
          <div class="conn-card-info">
            <div class="conn-card-title">${svc.name}</div>
            <div class="conn-card-desc">${svc.desc}</div>
          </div>
          <div class="conn-card-toggle">
            ${Components.Toggle('sync-' + key, svc.enabled)}
          </div>
        </div>`;
    });

    // 绑定 toggle 事件
    Object.keys(this._services).forEach(key => {
      Components.onToggle('sync-' + key, (on) => {
        this._services[key].enabled = on;
        App.renderCurrentPage();
      });
    });

    // 配置表单
    const configFormHtml = this._renderConfigForm();

    // 同步历史
    let historyHtml = '';
    logs.forEach((log, i) => {
      historyHtml += `
        <div class="sync-history-item">
          <div class="sync-history-dot ${log.status}"></div>
          <div class="sync-history-info">
            <div class="sync-history-title">${log.type} ${log.direction === 'push' ? '上传' : '下载'}</div>
            <div class="sync-history-detail">${log.details}</div>
          </div>
          <div class="sync-history-time">${log.time}</div>
        </div>`;
    });

    return `
      <div class="content-header animate-in">
        <div class="content-title">同步管理</div>
        <div class="content-subtitle">配置云同步服务，实现多设备数据同步</div>
      </div>
      <div class="content-body animate-in">
        <div class="sync-grid" style="margin-bottom:var(--sp-8)">
          ${connCardsHtml}
        </div>

        <div class="detail-layout">
          <div>
            <div class="section">
              <div class="section-title">${this._services[this._selectedService].name} 配置</div>
              ${configFormHtml}
            </div>
          </div>

          <div>
            <div class="section">
              <div class="section-title">同步历史</div>
              <div class="card">
                <div class="card-body" style="padding:var(--sp-3) var(--sp-4)">
                  <div class="sync-history-list">${historyHtml}</div>
                </div>
              </div>
            </div>

            <div class="section">
              <div class="section-title">手动同步</div>
              <div style="display:flex;gap:var(--sp-2)">
                <button class="btn btn-primary" style="flex:1" onclick="SyncPage.manualPush()">${Icons.upload(14)} 上传到云端</button>
                <button class="btn btn-secondary" style="flex:1" onclick="SyncPage.manualPull()">${Icons.download(14)} 从云端下载</button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
  },

  _renderConfigForm() {
    if (this._selectedService === 'webdav') {
      return `
        <div class="config-card">
          <div class="form-group">
            <label class="form-label">服务器地址</label>
            <input class="input" value="https://dav.jianguoyun.com/dav/" />
          </div>
          <div class="grid-2">
            <div class="form-group">
              <label class="form-label">用户名</label>
              <input class="input" value="user@example.com" />
            </div>
            <div class="form-group">
              <label class="form-label">应用密码</label>
              <input class="input" type="password" value="••••••••" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">远程路径</label>
            <input class="input" value="/合同红绿灯/" />
          </div>
          <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-4)">
            <button class="btn btn-primary" onclick="SyncPage.saveConfig()">${Icons.check(14)} 保存配置</button>
            <button class="btn btn-secondary" onclick="SyncPage.testConnection()">${Icons.refresh(14)} 测试连接</button>
          </div>
        </div>`;
    }
    if (this._selectedService === 'git') {
      return `
        <div class="config-card">
          <div class="form-group">
            <label class="form-label">仓库地址</label>
            <input class="input" placeholder="https://github.com/user/repo.git" />
          </div>
          <div class="form-group">
            <label class="form-label">分支</label>
            <input class="input" value="main" />
          </div>
          <div class="form-group">
            <label class="form-label">访问令牌</label>
            <input class="input" type="password" placeholder="ghp_xxxx" />
            <div class="form-hint">用于私有仓库的访问认证</div>
          </div>
          <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-4)">
            <button class="btn btn-primary" onclick="SyncPage.saveConfig()">${Icons.check(14)} 保存配置</button>
            <button class="btn btn-secondary" onclick="SyncPage.testConnection()">${Icons.refresh(14)} 测试连接</button>
          </div>
        </div>`;
    }
    if (this._selectedService === 's3') {
      return `
        <div class="config-card">
          <div class="grid-2">
            <div class="form-group">
              <label class="form-label">端点地址</label>
              <input class="input" placeholder="https://s3.amazonaws.com" />
            </div>
            <div class="form-group">
              <label class="form-label">存储桶</label>
              <input class="input" placeholder="clause-light" />
            </div>
          </div>
          <div class="grid-2">
            <div class="form-group">
              <label class="form-label">Access Key</label>
              <input class="input" type="password" />
            </div>
            <div class="form-group">
              <label class="form-label">Secret Key</label>
              <input class="input" type="password" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">区域</label>
            <input class="input" value="us-east-1" />
          </div>
          <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-4)">
            <button class="btn btn-primary" onclick="SyncPage.saveConfig()">${Icons.check(14)} 保存配置</button>
            <button class="btn btn-secondary" onclick="SyncPage.testConnection()">${Icons.refresh(14)} 测试连接</button>
          </div>
        </div>`;
    }
    return '';
  },

  selectService(key) {
    this._selectedService = key;
    App.renderCurrentPage();
  },

  async manualPush() {
    const res = await API.sync.push();
    if (res && res.success) Components.toast('上传成功', 'success');
  },

  async manualPull() {
    const res = await API.sync.pull();
    if (res && res.success) Components.toast('下载成功', 'success');
  },

  async saveConfig() {
    const res = await API.sync.updateConfig({ service: this._selectedService });
    if (res && res.success) Components.toast('配置已保存', 'success');
  },

  async testConnection() {
    Components.toast('正在测试连接...', 'info', 2000);
    setTimeout(() => Components.toast('连接测试成功（mock）', 'success'), 1000);
  },
};
