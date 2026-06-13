// ═══════════════════════════════════════════════════════════
// Page: Settings — 设置
// ═══════════════════════════════════════════════════════════

function PageSettings({ connection, onConnectionChange, theme, onThemeChange }) {
  const [connectType, setConnectType] = React.useState(
    connection.status === "connected" ? "lan" : "cloud"
  );
  const [ip, setIp] = React.useState(connection.serverIp || "192.168.1.100");
  const [port, setPort] = React.useState("8000");
  const [testStatus, setTestStatus] = React.useState(null); // null | "testing" | "ok" | "fail"
  const [showToast, setShowToast] = React.useState(false);
  const [scanStatus, setScanStatus] = React.useState(null); // null | "scanning" | "found" | "fail"

  const handleTest = () => {
    setTestStatus("testing");
    setTimeout(() => {
      setTestStatus(Math.random() > 0.3 ? "ok" : "fail");
    }, 1500);
  };

  const handleScan = () => {
    setScanStatus("scanning");
    setTimeout(() => {
      setScanStatus("found");
      setIp("192.168.1.105");
      setPort("8000");
    }, 2000);
  };

  const handleClearCache = () => {
    setShowToast(true);
  };

  return (
    <div className="page" data-screen-label="settings">
      <div className="top-bar">
        <div style={{ width: 60 }} />
        <div className="top-bar-title">设置</div>
        <div className="top-bar-spacer" />
      </div>

      <div className="page-content">
        {/* Server Connection */}
        <div className="settings-group">
          <div className="settings-group-title">服务器连接</div>
          <div style={{ padding: "var(--sp-3) var(--sp-4)" }}>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "var(--sp-2)" }}>
              连接方式
            </div>
            <div className="segmented-control">
              <button
                className={`segmented-item ${connectType === "lan" ? "active" : ""}`}
                onClick={() => setConnectType("lan")}
              >
                局域网直连
              </button>
              <button
                className={`segmented-item ${connectType === "scan" ? "active" : ""}`}
                onClick={() => setConnectType("scan")}
              >
                扫描连接
              </button>
              <button
                className={`segmented-item ${connectType === "cloud" ? "active" : ""}`}
                onClick={() => setConnectType("cloud")}
              >
                云端 API
              </button>
            </div>
          </div>

          {connectType === "lan" && (
            <div style={{ padding: "0 var(--sp-4) var(--sp-3)" }}>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "var(--sp-2)" }}>
                电脑 IP 地址
              </div>
              <input className="settings-input" value={ip} onChange={e => setIp(e.target.value)}
                placeholder="192.168.1.100" />
              <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", margin: "var(--sp-3) 0 var(--sp-2)" }}>
                端口
              </div>
              <input className="settings-input" value={port} onChange={e => setPort(e.target.value)}
                placeholder="8000" />
            </div>
          )}

          {connectType === "scan" && (
            <div style={{ padding: "0 var(--sp-4) var(--sp-3)", textAlign: "center" }}>
              {scanStatus === null && (
                <>
                  <div className="scan-frame">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                      <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="3" height="3" />
                      <line x1="21" y1="14" x2="21" y2="14.01" /><line x1="21" y1="21" x2="21" y2="21.01" />
                      <line x1="17" y1="21" x2="17" y2="21.01" />
                    </svg>
                    <span style={{ fontSize: "var(--text-xs)" }}>扫描电脑端二维码</span>
                  </div>
                  <button className="settings-btn" onClick={handleScan}>
                    📷 开始扫描
                  </button>
                </>
              )}
              {scanStatus === "scanning" && (
                <>
                  <div className="scan-frame scanning" style={{ position: "relative", overflow: "hidden" }}>
                    <div className="scan-line" />
                    <div className="scan-corner tl" /><div className="scan-corner tr" />
                    <div className="scan-corner bl" /><div className="scan-corner br" />
                    <div className="spinner" style={{ width: 32, height: 32, position: "relative", zIndex: 1 }} />
                    <span style={{ fontSize: "var(--text-sm)", color: "var(--accent)", fontWeight: 500, position: "relative", zIndex: 1 }}>扫描中...</span>
                  </div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
                    请将电脑端显示的二维码对准扫描框
                  </div>
                </>
              )}
              {scanStatus === "found" && (
                <>
                  <div className="scan-frame found">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--risk-green)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                    <span style={{ fontSize: "var(--text-sm)", color: "var(--risk-green-text)", fontWeight: 500 }}>已发现电脑</span>
                  </div>
                  <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "var(--sp-3)" }}>
                    {ip}:{port}
                  </div>
                  <button className="settings-btn" style={{ background: "var(--risk-green)" }} onClick={() => setScanStatus(null)}>
                    ✓ 确认连接
                  </button>
                </>
              )}
            </div>
          )}

          {connectType === "cloud" && (
            <div style={{ padding: "0 var(--sp-4) var(--sp-3)" }}>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "var(--sp-2)" }}>
                API 地址
              </div>
              <input className="settings-input" placeholder="https://api.example.com" />
              <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", margin: "var(--sp-3) 0 var(--sp-2)" }}>
                API Key
              </div>
              <input className="settings-input" type="password" placeholder="sk-..." />
            </div>
          )}

          {connectType !== "scan" && (
            <div style={{ padding: "0 var(--sp-4) var(--sp-4)" }}>
              <button className="settings-btn" onClick={handleTest}
                disabled={testStatus === "testing"}>
                {testStatus === "testing" ? (
                  <><div className="spinner" style={{ width: 16, height: 16 }} /> 测试中...</>
                ) : (
                  <><IconLink size={18} /> 测试连接</>
                )}
              </button>
              {testStatus === "ok" && (
                <div className="settings-status" style={{ color: "var(--risk-green-text)" }}>
                  <span className="connection-dot connected" /> 已连接
                </div>
              )}
              {testStatus === "fail" && (
                <div className="settings-status" style={{ color: "var(--risk-red-text)" }}>
                  <span className="connection-dot offline" /> 连接失败
                </div>
              )}
            </div>
          )}
        </div>

        {/* Appearance */}
        <div className="settings-group">
          <div className="settings-group-title">外观</div>
          <div style={{ padding: "var(--sp-3) var(--sp-4)" }}>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "var(--sp-2)" }}>
              主题
            </div>
            <div className="segmented-control">
              {[
                { key: "auto", label: "自动" },
                { key: "light", label: "亮色" },
                { key: "dark", label: "暗色" },
              ].map(opt => (
                <button
                  key={opt.key}
                  className={`segmented-item ${theme === opt.key ? "active" : ""}`}
                  onClick={() => onThemeChange(opt.key)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Data Management */}
        <div className="settings-group">
          <div className="settings-group-title">数据管理</div>
          <button className="settings-item" onClick={handleClearCache}>
            <span className="settings-item-label">清除本地缓存</span>
            <IconChevron size={16} color="var(--text-tertiary)" />
          </button>
          <button className="settings-item">
            <span className="settings-item-label">导出分析记录</span>
            <IconChevron size={16} color="var(--text-tertiary)" />
          </button>
        </div>

        {/* About */}
        <div className="settings-group">
          <div className="settings-group-title">关于</div>
          <div className="settings-item">
            <span className="settings-item-label">版本</span>
            <span className="settings-item-value">0.1.0</span>
          </div>
          <div className="settings-item">
            <span className="settings-item-label">ClauseLight 开源项目</span>
            <IconChevron size={16} color="var(--text-tertiary)" />
          </div>
        </div>
      </div>

      {showToast && <Toast message="缓存已清除" onClose={() => setShowToast(false)} />}
    </div>
  );
}

window.PageSettings = PageSettings;
