export default function AgentStatusBar({ steps, activeAgents, completedAgents }) {
  return (
    <div className="card">
      <div className="card-header">
        <span>🤖</span> Agent Pipeline
      </div>
      <div className="card-body agent-status">
        {steps.map((step, i) => {
          const isActive = activeAgents.includes(step.id)
          const isComplete = completedAgents.includes(step.id)
          const statusClass = isActive ? 'active' : isComplete ? 'complete' : 'pending'

          return (
            <div key={step.id} className={`agent-step ${statusClass}`}>
              <div className={`agent-dot ${isActive ? 'pulse' : ''}`} />
              <span style={{ fontSize: '14px' }}>{step.icon}</span>
              <span style={{ flex: 1 }}>{step.label}</span>
              {isComplete && <span style={{ fontSize: '11px' }}>✓</span>}
              {isActive && (
                <span style={{ fontSize: '10px', opacity: 0.7 }}>running</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
