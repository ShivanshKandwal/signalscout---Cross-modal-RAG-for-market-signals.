const TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'AMZN', 'META', 'JPM']

const SAMPLE_QUERIES = [
  'What are the main supply chain risks?',
  'What did management say about Q3 growth?',
  'Summarize recent earnings call sentiment',
  'What is the current technical trend?',
]

export default function QueryPanel({ ticker, onTickerChange, onSubmit, loading }) {
  const [query, setQuery] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (query.trim() && !loading) onSubmit(query.trim())
  }

  return (
    <div className="card">
      <div className="card-header">
        <span>⚡</span> Query
      </div>
      <div className="card-body query-section">
        {/* Ticker grid */}
        <div>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Select Ticker</p>
          <div className="ticker-selector">
            {TICKERS.map(t => (
              <button
                key={t}
                className={`ticker-btn ${ticker === t ? 'active' : ''}`}
                onClick={() => onTickerChange(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Query input */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <textarea
            className="query-input"
            placeholder="Ask about earnings, risks, sentiment, charts..."
            rows={4}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) handleSubmit(e) }}
          />

          {/* Sample queries */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {SAMPLE_QUERIES.map(q => (
              <button
                key={q}
                type="button"
                onClick={() => setQuery(q)}
                style={{
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  color: 'var(--text-muted)',
                  fontSize: '11px',
                  padding: '5px 10px',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.2s',
                }}
                onMouseOver={e => e.target.style.borderColor = 'var(--accent-primary)'}
                onMouseOut={e => e.target.style.borderColor = 'var(--border)'}
              >
                {q}
              </button>
            ))}
          </div>

          <button type="submit" className="submit-btn" disabled={loading || !query.trim()}>
            {loading ? (
              <>
                <div className="loading-dots">
                  <div className="loading-dot" />
                  <div className="loading-dot" />
                  <div className="loading-dot" />
                </div>
                <span>Analyzing...</span>
              </>
            ) : (
              <>
                <span>📡</span>
                <span>Generate Brief</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

import { useState } from 'react'
