// ═══════════════════════════════════════════════════════════
// ClauseLight Mobile — Shared Components
// ═══════════════════════════════════════════════════════════

// ── Risk Badge ──
function RiskBadge({ level, label }) {
  const labels = { red: "高风险", yellow: "中风险", green: "低风险" };
  return (
    <span className={`risk-badge ${level}`}>
      {label || labels[level] || level}
    </span>
  );
}

// ── Score Display ──
function ScoreDisplay({ score, size = "md" }) {
  const level = score >= 70 ? "green" : score >= 50 ? "yellow" : "red";
  const cls = size === "lg"
    ? `overview-score ${level}`
    : `contract-card-score ${level}`;
  return <span className={cls}>{score}</span>;
}

// ── Connection Bar ──
function ConnectionBar({ status, onClick }) {
  const labels = {
    connected: "已连接到电脑端",
    cloud: "使用云端 API",
    offline: "离线模式",
  };
  return (
    <div className={`connection-bar ${status}`} onClick={onClick}>
      <span className={`connection-dot ${status}`} />
      <span>{labels[status] || status}</span>
    </div>
  );
}

// ── Clause Card ──
function ClauseCard({ clause }) {
  const [showSuggestion, setShowSuggestion] = React.useState(false);
  const [showLegal, setShowLegal] = React.useState(false);
  const [feedback, setFeedback] = React.useState(null);

  return (
    <div className="clause-card">
      <div className={`clause-card-risk-bar ${clause.riskLevel}`}
        style={{ background: `var(--risk-${clause.riskLevel})` }} />
      <div className="clause-card-header">
        <span className="clause-card-num">{clause.number} {clause.title}</span>
        {clause.riskLevel !== "green" && <RiskBadge level={clause.riskLevel} />}
      </div>
      {clause.riskSummary && (
        <div className="clause-card-summary">{clause.riskSummary}</div>
      )}
      <div className="clause-card-explain">
        <div className="clause-card-explain-label">💡 大白话</div>
        {clause.plainExplanation}
      </div>
      {clause.suggestedClause && (
        <>
          <button
            className={`clause-card-expand ${showSuggestion ? "open" : ""}`}
            onClick={() => setShowSuggestion(!showSuggestion)}
          >
            📝 修改建议 <IconChevron />
          </button>
          {showSuggestion && (
            <div className="clause-card-expand-content suggestion">
              {clause.suggestedClause}
            </div>
          )}
        </>
      )}
      {clause.legalBasis && (
        <>
          <button
            className={`clause-card-expand ${showLegal ? "open" : ""}`}
            onClick={() => setShowLegal(!showLegal)}
          >
            ⚖️ 法律依据 <IconChevron />
          </button>
          {showLegal && (
            <div className="clause-card-expand-content legal">
              {clause.legalBasis}
            </div>
          )}
        </>
      )}
      <div className="clause-feedback">
        <button
          className={`feedback-btn ${feedback === "up" ? "selected" : ""}`}
          onClick={() => setFeedback(feedback === "up" ? null : "up")}
        >
          <IconThumbsUp /> 准确
        </button>
        <button
          className={`feedback-btn ${feedback === "down" ? "selected" : ""}`}
          onClick={() => setFeedback(feedback === "down" ? null : "down")}
        >
          <IconThumbsDown /> 不准确
        </button>
      </div>
    </div>
  );
}

// ── Search Input ──
function SearchInput({ value, onChange, placeholder }) {
  return (
    <div className="search-input-wrap">
      <IconSearch size={16} color="var(--text-tertiary)" className="search-icon" />
      <input
        className="search-input"
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder || "搜索..."}
      />
      {value && (
        <button className="search-clear" onClick={() => onChange("")}>
          <IconX size={14} />
        </button>
      )}
    </div>
  );
}

// ── Filter Chips ──
function FilterChips({ items, active, onSelect }) {
  return (
    <div className="chip-scroll">
      {items.map(item => (
        <button
          key={item.key}
          className={`chip ${active === item.key ? "active" : ""}`}
          onClick={() => onSelect(item.key)}
        >
          {item.dot && <span className={`risk-dot ${item.dot}`} />}
          {item.label}
        </button>
      ))}
    </div>
  );
}

// ── Toast ──
function Toast({ message, onClose }) {
  React.useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, []);
  return <div className="toast">{message}</div>;
}

// ── Dialog ──
function Dialog({ title, text, onConfirm, onCancel, confirmText }) {
  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <div className="dialog-title">{title}</div>
        <div className="dialog-text">{text}</div>
        <div className="dialog-actions">
          <button className="dialog-btn dialog-btn-cancel" onClick={onCancel}>取消</button>
          <button className="dialog-btn dialog-btn-confirm" onClick={onConfirm}>
            {confirmText || "确定"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Empty State ──
function EmptyState({ icon, text, buttonText, onAction }) {
  return (
    <div className="empty-state">
      {icon || <IconEmpty size={64} color="var(--text-tertiary)" />}
      <div className="empty-state-text">{text}</div>
      {buttonText && (
        <button className="empty-state-btn" onClick={onAction}>{buttonText}</button>
      )}
    </div>
  );
}

Object.assign(window, {
  RiskBadge, ScoreDisplay, ConnectionBar, ClauseCard,
  SearchInput, FilterChips, Toast, Dialog, EmptyState,
});
