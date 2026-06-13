// ═══════════════════════════════════════════════════════════
// Page: Home — 首页
// ═══════════════════════════════════════════════════════════

function PageHome({ onNavigate, connection, contracts }) {
  const recentContracts = contracts.slice(0, 5);
  const cameraRef = React.useRef(null);
  const fileRef = React.useRef(null);
  const [selectedFile, setSelectedFile] = React.useState(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      // 模拟：选完文件后跳转分析页
      onNavigate("analysis");
    }
  };

  return (
    <div className="page" data-screen-label="home">
      {/* 隐藏的文件输入 */}
      <input ref={cameraRef} type="file" accept="image/*" capture="environment"
        style={{ display: "none" }} onChange={handleFileChange} />
      <input ref={fileRef} type="file" accept="image/*,.pdf"
        style={{ display: "none" }} onChange={handleFileChange} />

      <div className="top-bar">
        <div style={{ width: 60 }} />
        <div className="top-bar-title">合同红绿灯</div>
        <button className="top-bar-action" onClick={() => onNavigate("settings")}>
          {document.documentElement.getAttribute("data-theme") === "dark"
            ? <IconSun size={20} />
            : <IconMoon size={20} />
          }
        </button>
      </div>

      <div className="page-content">
        {/* Upload Area */}
        <div className="upload-area">
          <button className="upload-btn upload-btn-photo"
            onClick={() => cameraRef.current?.click()}>
            <IconCamera size={32} color="#fff" />
            <span>拍照上传</span>
          </button>
          <button className="upload-btn upload-btn-file"
            onClick={() => fileRef.current?.click()}>
            <IconFile size={32} color="var(--text-secondary)" />
            <span>选择文件</span>
          </button>
        </div>

        {/* Connection Status */}
        <ConnectionBar
          status={connection.status}
          onClick={() => onNavigate("settings")}
        />

        {/* Recent Analysis */}
        <div className="section-title">最近分析</div>
        {recentContracts.length === 0 ? (
          <EmptyState
            text="还没有分析过合同，拍一张试试"
            buttonText="开始分析"
            onAction={() => onNavigate("analysis")}
          />
        ) : (
          recentContracts.map(c => (
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
          ))
        )}
      </div>
    </div>
  );
}

window.PageHome = PageHome;
