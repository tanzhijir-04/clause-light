/**
 * 共享 UI 组件 — 渲染函数
 */
const Components = (() => {

  /** 风险徽章 */
  function RiskBadge(level, label) {
    const labels = { red: '高风险', yellow: '中风险', green: '低风险' };
    return `<span class="risk-badge ${level}"><span class="risk-dot ${level}"></span>${label || labels[level] || level}</span>`;
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
        <div class="upload-zone-title">正在分析合同...</div>
        <div class="upload-zone-hint">OCR 识别 + AI 分析中，预计 30~60 秒</div>
      `;
    }

    // 同时显示全局 toast
    toast('正在分析：' + file.name + '，请稍候...', 'info', 5000);

    API.contracts.analyze(file)
      .then(res => {
        if (res && res.success) {
          toast('分析完成！正在跳转...', 'success', 2000);
          // 跳转到合同详情页
          setTimeout(() => {
            Router.navigate('contracts/' + res.contractId);
          }, 500);
        } else {
          // 问题 5 修复：后端返回 success:false + error
          const errMsg = res?.error || res?.detail || '未知错误';
          toast('分析失败：' + errMsg, 'error', 6000);
          if (uploadZone) uploadZone.innerHTML = originalContent;
        }
      })
      .catch(err => {
        toast('上传失败：' + err.message, 'error', 6000);
        if (uploadZone) uploadZone.innerHTML = originalContent;
      })
      .finally(() => {
        input.value = '';
      });
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
      <span class="toast-message">${message}</span>
      <span class="toast-close" onclick="this.parentElement.remove()">${Icons.x(14)}</span>`;
    container.appendChild(el);
    if (duration > 0) {
      setTimeout(() => {
        el.style.animation = 'toastOut 0.2s ease-out forwards';
        setTimeout(() => el.remove(), 200);
      }, duration);
    }
  }

  return {
    RiskBadge, StatCard, RiskDistBar, ScoreRing, Toggle,
    onToggle, handleToggle, ProgressBar, UploadZone, handleFileUpload,
    Sidebar, toast,
  };
})();
