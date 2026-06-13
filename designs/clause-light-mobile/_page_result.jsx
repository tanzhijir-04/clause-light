// ═══════════════════════════════════════════════════════════
// Page: Result — 分析结果
// ═══════════════════════════════════════════════════════════

function PageResult({ onNavigate, contract }) {
  const [filter, setFilter] = React.useState("all");
  const [showToast, setShowToast] = React.useState(false);

  const c = contract || MOCK_CONTRACTS[0];
  const clauses = c.clauses || [];

  const filtered = filter === "all"
    ? clauses
    : clauses.filter(cl => cl.riskLevel === filter);

  const scoreColor = c.score >= 70 ? "green" : c.score >= 50 ? "yellow" : "red";
  const totalClauses = clauses.length;
  const redPct = totalClauses ? (c.redCount / totalClauses) * 100 : 0;
  const yellowPct = totalClauses ? (c.yellowCount / totalClauses) * 100 : 0;
  const greenPct = totalClauses ? (c.greenCount / totalClauses) * 100 : 0;

  const advice = c.score >= 70
    ? "✅ 风险较低，可以签署"
    : c.score >= 50
    ? "⚠️ 建议修改后再签署"
    : "🚫 风险较高，强烈建议修改";

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: c.title, text: `合同分析报告：${c.title}，评分 ${c.score}` });
      } catch {}
    } else {
      setShowToast(true);
    }
  };

  return (
    <div className="page" data-screen-label="result">
      <div className="top-bar">
        <button className="top-bar-back" onClick={() => onNavigate("home")}>
          <IconBack /> 返回
        </button>
        <div className="top-bar-title">分析结果</div>
        <div className="top-bar-spacer" />
      </div>

      <div className="page-content" style={{ paddingBottom: 100 }}>
        {/* Overview Card */}
        <div className="overview-card">
          <ScoreDisplay score={c.score} size="lg" />
          <div className="overview-label">综合评分</div>
          <div className="overview-distribution">
            <div className="overview-dist-item">
              <span className="risk-dot red" /> <span style={{ color: "var(--risk-red-text)" }}>{c.redCount}</span>
            </div>
            <div className="overview-dist-item">
              <span className="risk-dot yellow" /> <span style={{ color: "var(--risk-yellow-text)" }}>{c.yellowCount}</span>
            </div>
            <div className="overview-dist-item">
              <span className="risk-dot green" /> <span style={{ color: "var(--risk-green-text)" }}>{c.greenCount}</span>
            </div>
          </div>
          <div className="overview-dist-bar">
            <div style={{ width: `${redPct}%`, background: "var(--risk-red)" }} />
            <div style={{ width: `${yellowPct}%`, background: "var(--risk-yellow)" }} />
            <div style={{ width: `${greenPct}%`, background: "var(--risk-green)" }} />
          </div>
          <div className="overview-advice">{advice}</div>
        </div>

        {/* Filter Tabs */}
        <div className="filter-tabs">
          {[
            { key: "all", label: `全部(${totalClauses})` },
            { key: "red", label: `红(${c.redCount})` },
            { key: "yellow", label: `黄(${c.yellowCount})` },
            { key: "green", label: `绿(${c.greenCount})` },
          ].map(tab => (
            <button
              key={tab.key}
              className={`filter-tab ${filter === tab.key ? "active" : ""}`}
              onClick={() => setFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Clause Cards */}
        {filtered.length === 0 ? (
          <EmptyState text="当前筛选条件下没有条款" />
        ) : (
          filtered.map(clause => (
            <ClauseCard key={clause.id} clause={clause} />
          ))
        )}
      </div>

      {/* Bottom Action Bar */}
      <div className="bottom-actions">
        <button className="action-btn action-btn-primary" onClick={handleShare}>
          <IconShare size={18} /> 分享报告
        </button>
        <button className="action-btn action-btn-secondary" onClick={() => onNavigate("home")}>
          <IconRefresh size={18} /> 重新分析
        </button>
      </div>

      {showToast && <Toast message="链接已复制到剪贴板" onClose={() => setShowToast(false)} />}
    </div>
  );
}

window.PageResult = PageResult;
