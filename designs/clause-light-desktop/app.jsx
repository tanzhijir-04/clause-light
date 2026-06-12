/* Main App */
const App = () => {
  const [page, setPage] = React.useState('dashboard');
  const [variant, setVariant] = React.useState('v1');
  const [theme, setTheme] = React.useState('light');

  React.useEffect(() => {
    document.documentElement.setAttribute('data-variant', variant);
    document.documentElement.setAttribute('data-theme', theme);
  }, [variant, theme]);

  const pages = { dashboard: DashboardPage, contracts: ContractsPage, knowledge: KnowledgePage, sync: SyncPage, settings: SettingsPage };
  const PageComponent = pages[page] || DashboardPage;

  return (
    <div className="app-layout">
      <Sidebar activePage={page} onNavigate={setPage} variant={variant} theme={theme} onThemeToggle={() => setTheme(t => t === 'light' ? 'dark' : 'light')} />
      <div className="main-content">
        <PageComponent />
      </div>
      <VariantSwitcher variant={variant} onVariantChange={setVariant} theme={theme} onThemeToggle={() => setTheme(t => t === 'light' ? 'dark' : 'light')} />
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);