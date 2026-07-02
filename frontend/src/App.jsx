import { useState } from 'react'
import QueryPanel from './components/QueryPanel'
import BriefPanel from './components/BriefPanel'
import CitationPanel from './components/CitationPanel'
import ConfidencePanel from './components/ConfidencePanel'
import ContradictionAlert from './components/ContradictionAlert'
import AgentStatusBar from './components/AgentStatusBar'

const AGENT_STEPS = [
  { id: 'orchestrator', label: 'Orchestrator', icon: '🎯' },
  { id: 'retrieval',    label: 'Retrieval Agent', icon: '🔍' },
  { id: 'analysis',     label: 'Analysis Agent', icon: '📊' },
  { id: 'citation',     label: 'Citation Agent', icon: '📎' },
  { id: 'contradiction',label: 'Contradiction Check', icon: '⚠️' },
  { id: 'critique',     label: 'Critique Agent', icon: '🧠' },
  { id: 'finalize',     label: 'Finalize', icon: '✅' },
]

export default function App() {
  const [ticker, setTicker] = useState('AAPL')
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeAgents, setActiveAgents] = useState([])
  const [completedAgents, setCompletedAgents] = useState([])
  const [activeCitation, setActiveCitation] = useState(null)

  const handleSubmit = async (query) => {
    setBrief(null)
    setLoading(true)
    setActiveAgents([])
    setCompletedAgents([])

    try {
      const { fetchEventSource } = await import('@microsoft/fetch-event-source')

      await fetchEventSource('/api/brief/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, ticker, stream: true }),

        onmessage(event) {
          if (event.data === '[DONE]') {
            setLoading(false)
            return
          }
          try {
            const data = JSON.parse(event.data)

            if (data.type === 'agent_start') {
              setActiveAgents([data.agent])
              setCompletedAgents(prev =>
                AGENT_STEPS.slice(0, AGENT_STEPS.findIndex(s => s.id === data.agent))
                  .map(s => s.id)
              )
            }

            if (data.type === 'complete') {
              setActiveAgents([])
              setCompletedAgents(AGENT_STEPS.map(s => s.id))
              setBrief(data.brief)
              setLoading(false)
            }
          } catch (e) { /* ignore parse errors */ }
        },

        onerror(err) {
          console.error('SSE error:', err)
          setLoading(false)
        },
      })
    } catch (err) {
      console.error('Request failed:', err)
      setLoading(false)
    }
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-logo">
          <div className="logo-icon">📡</div>
          <span>SignalScout</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="header-badge">MULTIMODAL RAG</span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {brief ? `${brief.num_chunks_retrieved} sources • ${brief.agent_hops} agent hops • ${brief.latency_ms?.toFixed(0)}ms` : 'Ready'}
          </span>
        </div>
      </header>

      {/* Sidebar */}
      <aside className="sidebar">
        <QueryPanel
          ticker={ticker}
          onTickerChange={setTicker}
          onSubmit={handleSubmit}
          loading={loading}
        />

        <AgentStatusBar
          steps={AGENT_STEPS}
          activeAgents={activeAgents}
          completedAgents={completedAgents}
        />

        {brief && (
          <ConfidencePanel confidence={brief.confidence} />
        )}
      </aside>

      {/* Main content */}
      <main className="main">
        {brief?.contradictions?.length > 0 && (
          <ContradictionAlert contradictions={brief.contradictions} />
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '20px', alignItems: 'start' }}>
          <BriefPanel
            brief={brief}
            loading={loading}
            onCitationClick={setActiveCitation}
          />
          <CitationPanel
            citations={brief?.citations || []}
            activeCitation={activeCitation}
            onCitationSelect={setActiveCitation}
          />
        </div>
      </main>
    </div>
  )
}
