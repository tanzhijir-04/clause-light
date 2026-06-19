/**
 * 共享 UI 组件 — 渲染函数
 */
const Components = (() => {

  /** XSS 防护：转义 HTML 特殊字符，防止用户数据被当作 HTML 解析 */
  function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const str = String(text);
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /** 风险徽章 */
  function RiskBadge(level, label) {
    const labels = { red: '高风险', yellow: '中风险', green: '低风险' };
    return `<span class="risk-badge ${escapeHtml(level)}"><span class="risk-dot ${escapeHtml(level)}"></span>${escapeHtml(label || labels[level] || level)}</span>`;
  }

  /** 统计卡片 */
  function StatCard(label, value, change, changeType, iconName) {
    const iconHtml = iconName && Icons[iconName] ? `<span class="stat-card-icon">${Icons[iconName](20)}</span>` : '';
    const changeHtml = change ? `<div class="stat-card-change ${changeType || 'neutral'}">${change}</div>` : '';
    return `<div class="stat-card">
      <div class="stat-card-top">
        <div>
          <div class="stat-card-label">${label}</div>
          <div class="stat-card-value">${value}</div>
        </div>
        ${iconHtml}
      </div>
      ${changeHtml}
    </div>`;
  }

  /** 风险分布条 */
  function RiskDistBar(red = 0, yellow = 0, green = 0) {
    const total = red + yellow + green;
    if (total === 0) return '<div class="risk-dist-bar"></div>';
    return `<div class="risk-dist-bar">
      ${red > 0 ? `<div class="risk-dist-segment red" style="flex:${red}"></div>` : ''}
      ${yellow > 0 ? `<div class="risk-dist-segment yellow" style="flex:${yellow}"></div>` : ''}
      ${green > 0 ? `<div class="risk-dist-segment green" style="flex:${green}"></div>` : ''}
    </div>`;
  }

  /** 评分圆环（SVG） */
  function ScoreRing(score, size = 64) {
    const r = (size - 8) / 2;
    const c = 2 * Math.PI * r;
    const offset = c - (score / 100) * c;
    const color = score >= 70 ? 'var(--risk-green)' : score >= 50 ? 'var(--risk-yellow)' : 'var(--risk-red)';
    return `<div class="score-ring" style="width:${size}px;height:${size}px">
      <svg width="${size}" height="${size}">
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="var(--border-subtle)" stroke-width="4"/>
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${color}" stroke-width="4" stroke-dasharray="${c}" stroke-dashoffset="${offset}" stroke-linecap="round" transform="rotate(-90 ${size/2} ${size/2})"/>
      </svg>
      <span class="score-ring-label" style="color:${color}">${score}</span>
    </div>`;
  }

  /** 开关 */
  function Toggle(id, on, className = '') {
    return `<div class="toggle-track ${on ? 'on' : ''} ${className}" data-toggle-id="${id}" onclick="Components.handleToggle('${id}')">
      <div class="toggle-thumb"></div>
    </div>`;
  }

  // 开关状态管理
  const _toggleCallbacks = {};

  function onToggle(id, fn) {
    _toggleCallbacks[id] = fn;
  }

  function handleToggle(id) {
    const el = document.querySelector(`[data-toggle-id="${id}"]`);
    if (!el) return;
    const isOn = el.classList.contains('on');
    el.classList.toggle('on');
    if (_toggleCallbacks[id]) {
      _toggleCallbacks[id](!isOn);
    }
  }

  /** 进度条 */
  function ProgressBar(value, max = 1, className = 'accent') {
    const pct = Math.min(100, (value / max) * 100);
    return `<div class="progress-bar"><div class="progress-bar-fill ${className}" style="width:${pct}%"></div></div>`;
  }

  /** 上传区域 */
  function UploadZone() {
    return `<div class="upload-zone" id="upload-zone">
      <div class="upload-zone-icon">${Icons.upload(48)}</div>
      <div class="upload-zone-title">快速上传合同</div>
      <div class="upload-zone-hint">拖放文件到此处，或点击选择文件</div>
      <button class="btn btn-primary" style="margin-top:var(--sp-2)" onclick="document.getElementById('file-input').click()">选择文件</button>
      <input type="file" id="file-input" accept=".pdf,.jpg,.jpeg,.png" style="display:none" onchange="Components.handleFileUpload(this)">
    </div>`;
  }

  function handleFileUpload(input) {
    const file = input.files[0];
    if (!file) return;

    // 显示 loading 状态（同时支持仪表盘 upload-zone 和合同管理页）
    const uploadZone = document.getElementById('upload-zone');
    const originalContent = uploadZone ? uploadZone.innerHTML : '';
    if (uploadZone) {
      uploadZone.innerHTML = `
        <div class="spinner"></div>
        <div class="upload-zone-title" id="upload-progress-title">正在上传...</div>
        <div class="upload-zone-hint" id="upload-progress-hint">请稍候</div>
        <div style="margin-top:12px;width:200px;height:4px;background:var(--border-default);border-radius:2px;overflow:hidden">
          <div id="upload-progress-bar" style="width:0%;height:100%;background:var(--accent);border-radius:2px;transition:width .3s"></div>
        </div>
      `;
    }

    // 同时显示全局 toast
    toast('正在分析：' + file.name + '，请稍候...', 'info', 5000);

    const progressSteps = {
      1: 'OCR 文字识别',
      2: '合同结构解析',
      3: '风险维度分析',
      4: '聚合评分',
      5: '生成报告',
    };

    API.contracts.analyzeStream(file, {
      onProgress(step, total, message, substep) {
        const pct = Math.round((step / total) * 100);
        const titleEl = document.getElementById('upload-progress-title');
        const hintEl = document.getElementById('upload-progress-hint');
        const barEl = document.getElementById('upload-progress-bar');
        if (titleEl) titleEl.textContent = message || (progressSteps[step] || '分析中...');
        // 如果有 substep（如下载进度），显示更详细的信息
        if (hintEl) hintEl.textContent = substep || `步骤 ${step}/${total}`;
        if (barEl) barEl.style.width = pct + '%';
      },
      onResult(data) {
        if (data.contractId) {
          toast('分析完成！正在跳转...', 'success', 2000);
          setTimeout(() => {
            Router.navigate('contracts/' + data.contractId);
          }, 500);
        }
      },
      onError(message) {
        toast('分析失败：' + message, 'error', 6000);
        if (uploadZone) uploadZone.innerHTML = originalContent;
      },
    });

    // 重置 file input
    input.value = '';
  }

  /** 侧边栏 */
  function Sidebar(activePage) {
    const navItems = [
      { section: '概览', items: [
        { key: 'dashboard', label: '仪表盘', icon: 'dashboard' },
      ]},
      { section: '管理', items: [
        { key: 'contracts', label: '合同管理', icon: 'fileText' },
        { key: 'knowledge', label: '知识库', icon: 'book' },
      ]},
      { section: '系统', items: [
        { key: 'sync', label: '同步管理', icon: 'cloud' },
        { key: 'models', label: '模型管理', icon: 'database' },
        { key: 'settings', label: '设置', icon: 'settings' },
      ]},
    ];

    let navHtml = '';
    navItems.forEach(group => {
      navHtml += `<div class="sidebar-section-label">${group.section}</div>`;
      group.items.forEach(item => {
        const active = activePage === item.key ? ' active' : '';
        navHtml += `<div class="sidebar-nav-item${active}" data-page="${item.key}">
          <span class="nav-icon">${Icons[item.icon](18)}</span>
          <span>${item.label}</span>
        </div>`;
      });
    });

    const themeIcon = Theme.get() === 'light' ? Icons.moon(14) : Icons.sun(14);
    const themeLabel = Theme.get() === 'light' ? '暗色模式' : '亮色模式';

    return `<div class="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-logo">
          <img src="/asset/合同红绿灯-transparent-mark.svg" alt="合同红绿灯" style="width:32px;height:32px;" />
        </div>
        <span class="sidebar-title">合同红绿灯</span>
      </div>
      <nav class="sidebar-nav">${navHtml}</nav>
      <div class="sidebar-footer">
        <div class="sidebar-status">
          <div class="status-dot"></div>
          <span>服务运行中</span>
        </div>
        <div class="sidebar-theme-toggle" onclick="App.toggleTheme()">
          ${themeIcon}
          <span>${themeLabel}</span>
        </div>
      </div>
    </div>`;
  }

  /** Toast 通知 */
  function _ensureToastContainer() {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function toast(message, type = 'info', duration = 3000) {
    const container = _ensureToastContainer();
    const iconMap = {
      success: Icons.check(16),
      error: Icons.x(16),
      info: Icons.info(16),
    };
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <span class="toast-icon">${iconMap[type] || iconMap.info}</span>
      <span class="toast-message">${escapeHtml(message)}</span>
      <span class="toast-close" onclick="this.parentElement.remove()">${Icons.x(14)}</span>`;
    container.appendChild(el);
    if (duration > 0) {
      setTimeout(() => {
        el.style.animation = 'toastOut 0.2s ease-out forwards';
        setTimeout(() => el.remove(), 200);
      }, duration);
    }
  }

  /** 可交互风险分布条（带点击筛选） */
  function RiskDistInteractive(red, yellow, green, filter, onFilter) {
    const total = red + yellow + green;
    if (total === 0) return '';
    return `<div style="display:flex;align-items:center;gap:var(--sp-3)">
      <div class="risk-dist-interactive" style="flex:1">
        ${red > 0 ? `<div class="risk-dist-seg red ${filter && filter !== 'red' ? 'dim' : ''}" style="width:${(red/total)*100}%" data-risk="red" onclick="${onFilter}('red')"></div>` : ''}
        ${yellow > 0 ? `<div class="risk-dist-seg yellow ${filter && filter !== 'yellow' ? 'dim' : ''}" style="width:${(yellow/total)*100}%" data-risk="yellow" onclick="${onFilter}('yellow')"></div>` : ''}
        ${green > 0 ? `<div class="risk-dist-seg green ${filter && filter !== 'green' ? 'dim' : ''}" style="width:${(green/total)*100}%" data-risk="green" onclick="${onFilter}('green')"></div>` : ''}
      </div>
      <div style="display:flex;gap:12px;font-size:11px;color:var(--text-secondary);white-space:nowrap">
        <span style="color:var(--risk-red);font-weight:${filter==='red'?700:400};cursor:pointer" onclick="${onFilter}('red')">红 ${red}</span>
        <span style="color:var(--risk-yellow);font-weight:${filter==='yellow'?700:400};cursor:pointer" onclick="${onFilter}('yellow')">黄 ${yellow}</span>
        <span style="color:var(--risk-green);font-weight:${filter==='green'?700:400};cursor:pointer" onclick="${onFilter}('green')">绿 ${green}</span>
      </div>
    </div>`;
  }

  /** 严重度条（10 格） */
  function SeverityBar(score, maxScore = 10) {
    const color = score >= 7 ? 'var(--risk-red)' : score >= 4 ? 'var(--risk-yellow)' : 'var(--risk-green)';
    let blocks = '';
    for (let i = 0; i < maxScore; i++) {
      blocks += `<div class="severity-block" style="${i < score ? 'background:' + color : ''}"></div>`;
    }
    return `<div class="severity-bar">
      <div class="severity-blocks">${blocks}</div>
      <span class="severity-text">${score}/${maxScore}</span>
    </div>`;
  }

  return {
    escapeHtml,
    RiskBadge, StatCard, RiskDistBar, ScoreRing, Toggle,
    onToggle, handleToggle, ProgressBar, UploadZone, handleFileUpload,
    Sidebar, toast, RiskDistInteractive, SeverityBar,
  };
})();
