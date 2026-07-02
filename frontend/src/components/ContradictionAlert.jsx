export default function ContradictionAlert({ contradictions }) {
  if (!contradictions?.length) return null

  return (
    <div>
      {contradictions.map((c, i) => (
        <div key={c.id || i} className="contradiction-alert" style={{ marginBottom: '12px' }}>
          <div className="contradiction-header">
            <span>⚠️</span>
            <span>Cross-Modal Contradiction Detected</span>
            <span className={`severity-badge ${c.severity}`} style={{ marginLeft: 'auto' }}>
              {c.severity} severity
            </span>
          </div>

          <div className="contradiction-pair">
            <div className="contradiction-side">
              <div className="contradiction-side-label" style={{ color: '#a78bfa' }}>
                🎙️ Management Statement (Audio)
              </div>
              <p>{c.audio_claim}</p>
            </div>
            <div className="contradiction-side">
              <div className="contradiction-side-label" style={{ color: 'var(--accent-primary)' }}>
                📄 SEC Filing (Document)
              </div>
              <p>{c.document_claim}</p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span>NLI Score: {(c.nli_score * 100).toFixed(0)}%</span>
            {c.explanation && <span>· {c.explanation}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}
