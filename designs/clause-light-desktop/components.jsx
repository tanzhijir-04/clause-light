/* Shared UI components */
const RiskBadge = ({ level, label }) => (
  <span className={`risk-badge ${level}`}>
    <span className={`risk-dot ${level}`}></span>
    {label || (level === 'red' ? '高风险' : level === 'yellow' ? '中风险' : '低风险')}
  </span>
);

const StatCard = ({ label, value, change, changeType, icon: IconComp }) => (
  <div className="stat-card">
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <div className="stat-card-label">{label}</div>
        <div className="stat-card-value">{value}</div>
      </div>
      {IconComp && <IconComp size={20} />}
    </div>
    {change && <div className={`stat-card-change ${changeType || 'neutral'}`}>{change}</div>}
  </div>
);

const RiskDistBar = ({ red = 0, yellow = 0, green = 0 }) => {
  const total = red + yellow + green;
  if (total === 0) return <div className="risk-dist-bar"></div>;
  return (
    <div className="risk-dist-bar">
      {red > 0 && <div className="risk-dist-segment red" style={{ flex: red }}></div>}
      {yellow > 0 && <div className="risk-dist-segment yellow" style={{ flex: yellow }}></div>}
      {green > 0 && <div className="risk-dist-segment green" style={{ flex: green }}></div>}
    </div>
  );
};

const ScoreRing = ({ score, size = 64 }) => {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  const color = score >= 70 ? 'var(--risk-green)' : score >= 50 ? 'var(--risk-yellow)' : 'var(--risk-red)';
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--border-subtle)" strokeWidth="4" />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="4" strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <span className="score-ring-label" style={{ color }}>{score}</span>
    </div>
  );
};

const Toggle = ({ on, onChange }) => (
  <div className={`toggle-track ${on ? 'on' : ''}`} onClick={() => onChange(!on)}>
    <div className="toggle-thumb"></div>
  </div>
);

const Sidebar = ({ activePage, onNavigate, variant, theme, onThemeToggle }) => (
  <div className="sidebar">
    <div className="sidebar-header">
      <div className="sidebar-logo">
        <img src="../asset/合同红绿灯-transparent-mark.svg" alt="合同红绿灯" style={{width: 32, height: 32}} />
      </div>
      <span className="sidebar-title">合同红绿灯</span>
    </div>
    <nav className="sidebar-nav">
      <div className="sidebar-section-label">概览</div>
      <div className={`sidebar-item ${activePage === 'dashboard' ? 'active' : ''}`} onClick={() => onNavigate('dashboard')}>
        <IconDashboard size={18} className="sidebar-item-icon" />
        <span>仪表盘</span>
      </div>
      <div className="sidebar-section-label">管理</div>
      <div className={`sidebar-item ${activePage === 'contracts' ? 'active' : ''}`} onClick={() => onNavigate('contracts')}>
        <IconFileText size={18} className="sidebar-item-icon" />
        <span>合同管理</span>
      </div>
      <div className={`sidebar-item ${activePage === 'knowledge' ? 'active' : ''}`} onClick={() => onNavigate('knowledge')}>
        <IconBook size={18} className="sidebar-item-icon" />
        <span>知识库</span>
      </div>
      <div className="sidebar-section-label">系统</div>
      <div className={`sidebar-item ${activePage === 'sync' ? 'active' : ''}`} onClick={() => onNavigate('sync')}>
        <IconCloud size={18} className="sidebar-item-icon" />
        <span>同步管理</span>
      </div>
      <div className={`sidebar-item ${activePage === 'settings' ? 'active' : ''}`} onClick={() => onNavigate('settings')}>
        <IconSettings size={18} className="sidebar-item-icon" />
        <span>设置</span>
      </div>
    </nav>
    <div className="sidebar-footer">
      <div className="sidebar-status">
        <div className="status-dot"></div>
        <span>服务运行中</span>
      </div>
    </div>
  </div>
);

const VariantSwitcher = ({ variant, onVariantChange, theme, onThemeToggle }) => (
  <div className="variant-switcher">
    <button className={variant === 'v1' ? 'active' : ''} onClick={() => onVariantChange('v1')}>V1 Notion</button>
    <button className={variant === 'v2' ? 'active' : ''} onClick={() => onVariantChange('v2')}>V2 Linear</button>
    <div className="variant-divider"></div>
    <button onClick={onThemeToggle} title={theme === 'light' ? '切换到暗色主题' : '切换到亮色主题'}>
      {theme === 'light' ? <IconMoon size={14} /> : <IconSun size={14} />}
    </button>
  </div>
);

Object.assign(window, { RiskBadge, StatCard, RiskDistBar, ScoreRing, Toggle, Sidebar, VariantSwitcher });