// ═══════════════════════════════════════════════════════════
// Page: Analysis — 分析中
// ═══════════════════════════════════════════════════════════

function PageAnalysis({ onNavigate, onComplete }) {
  const [currentStep, setCurrentStep] = React.useState(0);
  const [progress, setProgress] = React.useState(0);
  const [results, setResults] = React.useState([]);
  const [showDialog, setShowDialog] = React.useState(false);
  const [complete, setComplete] = React.useState(false);

  const steps = ANALYSIS_STEPS;
  const clauses = MOCK_CONTRACTS[0].clauses;

  React.useEffect(() => {
    // Simulate analysis progress
    const timers = [];
    const totalDuration = 6000;
    const stepDuration = totalDuration / steps.length;

    steps.forEach((step, i) => {
      timers.push(setTimeout(() => {
        setCurrentStep(i);
        setProgress(Math.round(((i + 1) / steps.length) * 100));
      }, stepDuration * (i + 1)));
    });

    // Add results one by one
    clauses.forEach((clause, i) => {
      timers.push(setTimeout(() => {
        setResults(prev => [...prev, clause]);
      }, 800 + i * 600));
    });

    // Complete
    timers.push(setTimeout(() => {
      setComplete(true);
    }, totalDuration + 500));

    return () => timers.forEach(clearTimeout);
  }, []);

  const handleBack = () => {
    if (results.length > 0) {
      setShowDialog(true);
    } else {
      onNavigate("home");
    }
  };

  return (
    <div className="page" data-screen-label="analysis">
      <div className="top-bar">
        <button className="top-bar-back" onClick={handleBack}>
          <IconBack /> 返回
        </button>
        <div className="top-bar-title">分析中</div>
        <div className="top-bar-spacer" />
      </div>

      {/* Progress Area */}
      <div className="analysis-progress">
        <div className="analysis-current-step">
          <div className="spinner" />
          <span>{steps[currentStep]?.label || "准备中"}...</span>
        </div>

        {/* Step Progress */}
        <div className="step-progress">
          {steps.map((step, i) => (
            <React.Fragment key={step.key}>
              <div className={`step-node ${
                i < currentStep ? "done" : i === currentStep ? "active" : ""
              }`} />
              {i < steps.length - 1 && (
                <div className={`step-line ${i < currentStep ? "done" : ""}`} />
              )}
            </React.Fragment>
          ))}
        </div>
        <div className="step-labels">
          {steps.map((step, i) => (
            <span key={step.key} className={`step-label ${
              i < currentStep ? "done" : i === currentStep ? "active" : ""
            }`}>{step.label}</span>
          ))}
        </div>

        {/* Overall Progress Bar */}
        <div className="progress-bar-wrap">
          <div className="progress-bar-track">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-bar-text">{progress}%</span>
        </div>
      </div>

      {/* Realtime Results */}
      {results.length > 0 && (
        <div className="realtime-results">
          <div className="section-title" style={{ padding: "0 var(--sp-4)" }}>实时结果</div>
          {results.map((clause, i) => (
            <div key={clause.id} className="result-card-mini" style={{ animationDelay: `${i * 0.05}s` }}>
              <div className={`result-card-mini-risk ${clause.riskLevel}`}
                style={{ background: `var(--risk-${clause.riskLevel})` }} />
              <div className="result-card-mini-body">
                <div className="result-card-mini-header">
                  <span className="result-card-mini-num">{clause.number}</span>
                  <span className="result-card-mini-title">{clause.title}</span>
                  <RiskBadge level={clause.riskLevel} />
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginTop: 2 }}>
                  {clause.riskSummary || "无风险"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Complete Banner */}
      {complete && (
        <div className="complete-banner" onClick={() => onComplete()}>
          ✅ 分析完成，点击查看结果
        </div>
      )}

      {showDialog && (
        <Dialog
          title="离开分析？"
          text="分析正在进行中，确定要离开吗？"
          onConfirm={() => onNavigate("home")}
          onCancel={() => setShowDialog(false)}
          confirmText="确定离开"
        />
      )}
    </div>
  );
}

window.PageAnalysis = PageAnalysis;
