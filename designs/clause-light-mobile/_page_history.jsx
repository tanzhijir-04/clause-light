// ═══════════════════════════════════════════════════════════
// Page: History — 历史记录
// ═══════════════════════════════════════════════════════════

function PageHistory({ onNavigate, contracts }) {
  const [search, setSearch] = React.useState("");
  const [riskFilter, setRiskFilter] = React.useState("all");

  // Filter contracts
  const filtered = contracts.filter(c => {
    const matchSearch = !search || c.title.includes(search) || c.type.includes(search);
    const matchRisk = riskFilter === "all" || c.riskLevel === riskFilter;
    return matchSearch && matchRisk;
  });

  // Group by month
  const grouped = {};
  filtered.forEach(c => {
    const month = c.createdAt.substring(0, 7); // "2026-06"
    if (!grouped[month]) grouped[month] = [];
    grouped[month].push(c);
  });

  const monthLabels = Object.keys(grouped).sort().reverse();

  return (
    <div className="page" data-screen-label="history">
      <div className="top-bar">
        <div style={{ width: 60 }} />
        <div className="top-bar-title">历史记录</div>
        <div className="top-bar-spacer" />
      </div>

      <div className="page-content">
        {/* Search */}
        <SearchInput value={search} onChange={setSearch} placeholder="搜索合同..." />

        {/* Risk Filter Chips */}
        <FilterChips
          active={riskFilter}
          onSelect={setRiskFilter}
          items={[
            { key: "all", label: "全部" },
            { key: "red", label: "高风险", dot: "red" },
            { key: "yellow", label: "中风险", dot: "yellow" },
            { key: "green", label: "低风险", dot: "green" },
          ]}
        />

        {/* Grouped Records */}
        {monthLabels.length === 0 ? (
          <EmptyState
            text="还没有分析记录"
            buttonText="拍一张合同试试"
            onAction={() => onNavigate("home")}
          />
        ) : (
          monthLabels.map(month => {
            const [y, m] = month.split("-");
            return (
              <div key={month}>
                <div className="month-header">{y}年{parseInt(m)}月</div>
                {grouped[month].map(c => (
                  <div key={c.id} className="contract-card"
                    onClick={() => onNavigate("result", c)}>
                    <div className={`contract-card-risk-bar ${c.riskLevel}`} />
                    <div className="contract-card-body">
                      <div className="contract-card-header">
                        <span className="contract-card-title">{c.title}</span>
                        <ScoreDisplay score={c.score} />
                      </div>
                      <div className="contract-card-meta">
                        <span className="contract-card-type">{c.type}</span>
                        <div className="contract-card-risk-dots">
                          <span className="risk-dot red" /> {c.redCount}
                          <span className="risk-dot yellow" /> {c.yellowCount}
                          <span className="risk-dot green" /> {c.greenCount}
                        </div>
                        <span>{c.createdAt}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

window.PageHistory = PageHistory;
