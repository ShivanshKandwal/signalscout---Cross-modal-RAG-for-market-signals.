export default function CitationPanel({ citations, activeCitation, onCitationSelect }) {
  if (!citations.length) return null

  return (
    <div className="card" style={{ position: 'sticky', top: 0 }}>
      <div className="card-header">
        <span>📎</span> Sources ({citations.length})
      </div>
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '70vh', overflowY: 'auto' }}>
        {citations.map((citation, i) => (
          <div
            key={citation.id || i}
            className="citation-item"
            style={activeCitation === i ? { borderColor: 'var(--accent-primary)', background: 'rgba(99,130,255,0.08)' } : {}}
            onClick={() => onCitationSelect(activeCitation === i ? null : i)}
          >
            <div className="citation-header">
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
                [{i + 1}]
              </span>
              <span className={`modality-badge ${citation.modality}`}>
                {citation.modality === 'audio' && '🎙️'}
                {citation.modality === 'document' && '📄'}
                {citation.modality === 'news' && '📰'}
                {citation.modality === 'image' && '📊'}
                {' '}{citation.modality}
              </span>
              {citation.confidence > 0 && (
                <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {(citation.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>

            {activeCitation === i && (
              <>
                <div className="citation-excerpt">
                  "{citation.chunk_excerpt}"
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {citation.ticker}
                  {citation.filed_date && ` · ${citation.filed_date}`}
                  {citation.source_url && (
                    <> · <a href={citation.source_url} target="_blank" rel="noreferrer"
                      style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>
                      Source ↗
                    </a></>
                  )}
                </div>
              </>
            )}

            {activeCitation !== i && (
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {citation.chunk_excerpt}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
