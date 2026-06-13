// ═══════════════════════════════════════════════════════════
// App — Router + Tab Navigation + Theme Toggle
// ═══════════════════════════════════════════════════════════

function App() {
  const [page, setPage] = React.useState("home");
  const [pageData, setPageData] = React.useState(null);
  const [theme, setTheme] = React.useState("auto");
  const [connection, setConnection] = React.useState(MOCK_CONNECTION);

  // Apply theme
  React.useEffect(() => {
    const root = document.documentElement;
    if (theme === "auto") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      root.setAttribute("data-theme", mq.matches ? "dark" : "light");
      const handler = (e) => root.setAttribute("data-theme", e.matches ? "dark" : "light");
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }
    root.setAttribute("data-theme", theme);
  }, [theme]);

  const navigate = (p, data) => {
    setPage(p);
    setPageData(data || null);
  };

  const handleAnalysisComplete = () => {
    navigate("result", MOCK_CONTRACTS[0]);
  };

  const TABS = [
    { key: "home", label: "首页", icon: IconHome },
    { key: "history", label: "历史", icon: IconHistory },
    { key: "knowledge", label: "知识库", icon: IconBook },
    { key: "settings", label: "设置", icon: IconSettings },
  ];

  const isTabPage = ["home", "history", "knowledge", "settings"].includes(page);

  const renderPage = () => {
    switch (page) {
      case "home":
        return <PageHome onNavigate={navigate} connection={connection} contracts={MOCK_CONTRACTS} />;
      case "analysis":
        return <PageAnalysis onNavigate={navigate} onComplete={handleAnalysisComplete} />;
      case "result":
        return <PageResult onNavigate={navigate} contract={pageData} />;
      case "history":
        return <PageHistory onNavigate={navigate} contracts={MOCK_CONTRACTS} />;
      case "knowledge":
        return <PageKnowledge />;
      case "settings":
        return <PageSettings
          connection={connection}
          onConnectionChange={setConnection}
          theme={theme}
          onThemeChange={setTheme}
        />;
      default:
        return <PageHome onNavigate={navigate} connection={connection} contracts={MOCK_CONTRACTS} />;
    }
  };

  return (
    <>
      {renderPage()}
      {isTabPage && (
        <nav className="tab-bar">
          {TABS.map(tab => {
            const IconComp = tab.icon;
            return (
              <button
                key={tab.key}
                className={`tab-item ${page === tab.key ? "active" : ""}`}
                onClick={() => navigate(tab.key)}
              >
                <IconComp size={22} color={page === tab.key ? "var(--accent)" : "var(--text-tertiary)"} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
