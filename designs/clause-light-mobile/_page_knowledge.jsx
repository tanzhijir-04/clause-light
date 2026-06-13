// ═══════════════════════════════════════════════════════════
// Page: Knowledge — 知识库
// ═══════════════════════════════════════════════════════════

function PageKnowledge() {
  const [tab, setTab] = React.useState("rules");
  const [search, setSearch] = React.useState("");
  const [categoryFilter, setCategoryFilter] = React.useState("all");
  const [expandedRule, setExpandedRule] = React.useState(null);

  const rules = MOCK_RULES.filter(r => {
    const matchSearch = !search || r.ruleText.includes(search);
    const matchCat = categoryFilter === "all" || r.category === categoryFilter;
    return matchSearch && matchCat;
  });

  const categories = [...new Set(MOCK_RULES.map(r => r.category))];

  return (
    <div className="page" data-screen-label="knowledge">
      <div className="top-bar">
        <div style={{ width: 60 }} />
        <div className="top-bar-title">知识库</div>
        <div className="top-bar-spacer" />
      </div>

      <div className="page-content">
        {/* Stats */}
        <div className="knowledge-stats">
          <span><span className="knowledge-stat">{MOCK_RULES.length}</span> 条规则</span>
          <span style={{ color: "var(--border-default)" }}>|</span>
          <span><span className="knowledge-stat">{MOCK_LAWS.length}</span> 部法规</span>
        </div>

        {/* Tab Bar */}
        <div className="filter-tabs" style={{ marginBottom: "var(--sp-3)" }}>
          <button className={`filter-tab ${tab === "rules" ? "active" : ""}`}
            onClick={() => setTab("rules")}>
            规则库
          </button>
          <button className={`filter-tab ${tab === "laws" ? "active" : ""}`}
            onClick={() => setTab("laws")}>
            法规库
          </button>
        </div>

        {tab === "rules" ? (
          <>
            <SearchInput value={search} onChange={setSearch} placeholder="搜索规则..." />
            <FilterChips
              active={categoryFilter}
              onSelect={setCategoryFilter}
              items={[
                { key: "all", label: "全部" },
                ...categories.map(c => ({ key: c, label: c })),
              ]}
            />
            {rules.map(rule => (
              <div key={rule.id} className="rule-card"
                onClick={() => setExpandedRule(expandedRule === rule.id ? null : rule.id)}>
                <div className="rule-card-tags">
                  <RiskBadge level={rule.riskLevel} />
                  <span className="contract-card-type">{rule.category}</span>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginLeft: "auto" }}>
                    置信度 {rule.confidence}
                  </span>
                </div>
                <div className={`rule-card-text ${expandedRule === rule.id ? "expanded" : ""}`}>
                  {rule.ruleText}
                </div>
                <div className="rule-card-confidence">
                  已使用 {rule.usageCount} 次 · {rule.source === "auto_learned" ? "自动学习" : "手动添加"}
                </div>
              </div>
            ))}
          </>
        ) : (
          <>
            {MOCK_LAWS.map(law => (
              <div key={law.id} className="rule-card">
                <div className="rule-card-tags">
                  <span className="contract-card-type" style={{ background: "var(--accent-subtle)", color: "var(--accent)" }}>
                    {law.shortName}
                  </span>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginLeft: "auto" }}>
                    {law.articleCount} 条
                  </span>
                </div>
                <div className="rule-card-text" style={{ WebkitLineClamp: "unset" }}>
                  {law.name}
                </div>
                <div className="rule-card-confidence">
                  {law.tags.join(" · ")}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

window.PageKnowledge = PageKnowledge;
