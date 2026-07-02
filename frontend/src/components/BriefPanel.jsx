import ReactMarkdown from 'react-markdown'

export default function BriefPanel({ brief, loading, onCitationClick }) {
  if (loading && !brief) {
    return (
      <div className="card">
        <div className="card-header"><span>📋</span> Investment Brief</div>
        <div className="card-body">
          <div className="empty-state">
            <div className="loading-dots">
              <div className="loading-dot" />
              <div className="loading-dot" />
              <div className="loading-dot" />
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
              Agents working on your brief...
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (!brief) {
    return (
      <div className="card">
        <div className="card-header"><span>📋</span> Investment Brief</div>
        <div className="card-body">
          <div className="empty-state">
            <div className="empty-icon">📡</div>
            <div className="empty-title">No brief yet</div>
            <div className="empty-desc">
              Select a ticker, enter your question, and hit Generate Brief to run the multi-agent pipeline.
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <span>📋</span>
        <span>Investment Brief — {brief.ticker}</span>
        <span
          className={`sentiment-badge ${brief.sentiment}`}
          style={{ marginLeft: 'auto' }}
        >
          {brief.sentiment}
        </span>
      </div>
      <div className="card-body">
        <div className="brief-content">
          <ReactMarkdown
            components={{
              // Convert [N] citation refs to clickable badges
              text: ({ children }) => {
                if (typeof children !== 'string') return <>{children}</>
                return children.replace(/\[(\d+)\]/g, (match, n) => (
                  `__CITE_${n}__`
                )).split('__').map((part, i) => {
                  const citeMatch = part.match(/^CITE_(\d+)$/)
                  if (citeMatch) {
                    const idx = parseInt(citeMatch[1]) - 1
                    return (
                      <span
                        key={i}
                        className="citation-ref"
                        onClick={() => onCitationClick(idx)}
                      >
                        {citeMatch[1]}
                      </span>
                    )
                  }
                  return part
                })
              }
            }}
          >
            {brief.brief_markdown}
          </ReactMarkdown>
        </div>

        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          gap: '16px',
          fontSize: '12px',
          color: 'var(--text-muted)',
        }}>
          <span>📎 {brief.citations?.length || 0} citations</span>
          <span>🔍 {brief.num_chunks_retrieved} sources</span>
          <span>🤖 {brief.agent_hops} hops</span>
          <span>⏱ {brief.latency_ms?.toFixed(0)}ms</span>
          {brief.confidence?.overall > 0 && (
            <span>🎯 {(brief.confidence.overall * 100).toFixed(0)}% confidence</span>
          )}
        </div>
      </div>
    </div>
  )
}
