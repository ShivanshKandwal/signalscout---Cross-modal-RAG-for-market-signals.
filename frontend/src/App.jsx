import { useState, useEffect } from "react"
import QueryPanel from "./components/QueryPanel"
import BriefPanel from "./components/BriefPanel"
import CitationPanel from "./components/CitationPanel"
import ConfidencePanel from "./components/ConfidencePanel"
import ContradictionAlert from "./components/ContradictionAlert"
import AgentStatusBar from "./components/AgentStatusBar"
import TechnicalGuide from "./components/TechnicalGuide"
import BullishMeter from "./components/BullishMeter"
import { GridBeam } from "./components/ui/grid-beam"
import ShaderBackground from "./components/ui/shader-background"
import { Radio, BarChart3, Clock, AlertOctagon, Coins, Cpu } from "lucide-react"

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

const AGENT_STEPS = [
  { id: "orchestrator", label: "Orchestrator", icon: "Target" },
  { id: "retrieval",    label: "Retrieval Agent", icon: "Search" },
  { id: "analysis",     label: "Analysis Agent", icon: "BarChart3" },
  { id: "citation",     label: "Citation Agent", icon: "Link2" },
  { id: "contradiction",label: "Contradiction Check", icon: "AlertTriangle" },
  { id: "critique",     label: "Critique Agent", icon: "Brain" },
  { id: "finalize",     label: "Finalize", icon: "CheckCircle2" },
]

export default function App() {
  const [ticker, setTicker] = useState("AAPL")
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeAgents, setActiveAgents] = useState([])
  const [completedAgents, setCompletedAgents] = useState([])
  const [activeCitation, setActiveCitation] = useState(null)
  const [analytics, setAnalytics] = useState(null)

  const fetchAnalytics = async () => {
    try {
      const res = await fetch(`${API_URL}/api/analytics/system`)
      const data = await res.json()
      setAnalytics(data)
    } catch (e) {
      console.error("Failed to fetch analytics:", e)
    }
  }

  useEffect(() => {
    fetchAnalytics()
  }, [])

  const handleSubmit = async (query) => {
    setBrief(null)
    setLoading(true)
    setActiveAgents([])
    setCompletedAgents([])

    try {
      const { fetchEventSource } = await import("@microsoft/fetch-event-source")

      await fetchEventSource(`${API_URL}/api/brief/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, ticker, stream: true }),

        onmessage(event) {
          if (event.data === "[DONE]") {
            setLoading(false)
            return
          }
          try {
            const data = JSON.parse(event.data)

            if (data.type === "agent_start") {
              setActiveAgents([data.agent])
              setCompletedAgents((prev) =>
                AGENT_STEPS.slice(0, AGENT_STEPS.findIndex((s) => s.id === data.agent)).map((s) => s.id)
              )
            }

            if (data.type === "complete") {
              setActiveAgents([])
              setCompletedAgents(AGENT_STEPS.map((s) => s.id))
              setBrief(data.brief)
              setLoading(false)
              fetchAnalytics()
            }
          } catch (e) {
            /* ignore parse errors */
          }
        },

        onerror(err) {
          console.error("SSE error:", err)
          setLoading(false)
          fetchAnalytics()
        },
      })
    } catch (err) {
      console.error("Request failed:", err)
      setLoading(false)
      fetchAnalytics()
    }
  }

  return (
    <div className="relative w-full min-h-screen overflow-x-hidden text-neutral-200 bg-transparent">
      
      {/* ── 1. Real-Time WebGL Fluid Shader Gradient Background (60fps) ────── */}
      <div className="fixed inset-0 z-[-2] pointer-events-none select-none">
        <ShaderBackground />
        <div className="absolute inset-0 vignette-overlay z-[-1]" />
      </div>

      {/* ── 2. Header Grid Header Layout ────────────────────────────────────────── */}
      <header className="relative z-10 w-full border-b border-white/5 bg-neutral-950/40 backdrop-blur-md">
        <GridBeam rows={3} cols={8} strength={0.35} duration={6} className="w-full py-4 px-6 md:px-12">
          <div className="flex items-center justify-between z-20 relative w-full">
            <div className="flex items-center gap-3.5">
              <div className="p-2.5 bg-pink-500/10 border border-pink-500/30 text-pink-400 rounded-xl shadow-[0_0_15px_rgba(212,68,239,0.25)] flex items-center justify-center">
                <Radio className="w-5 h-5 text-pink-400 animate-pulse" />
              </div>
              <div>
                <h1 className="text-xl md:text-2xl font-black tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-neutral-100 via-pink-400 to-indigo-400 uppercase font-title">
                  SignalScout
                </h1>
                <p className="text-[10px] md:text-xs text-neutral-400 font-extrabold uppercase tracking-widest font-title">
                  Cross-Modal RAG Market Analysis Platform
                </p>
              </div>
            </div>
            {/* Morphing Dynamic Island Notch is moved next to input panel */}
          </div>
        </GridBeam>
      </header>

      {/* ── 3. Main Dashboard Workspace Layout ─────────────────────────────── */}
      <main className="relative z-10 max-w-7xl mx-auto px-4 md:px-8 py-8 flex flex-col gap-8">
        
        {/* CENTER STAGE: Huge Prompt search console & Pipeline Stage */}
        <section className="w-full flex justify-center z-20">
          <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-[1fr_300px] gap-6 items-center">
            <QueryPanel
              ticker={ticker}
              onTickerChange={setTicker}
              onSubmit={handleSubmit}
              loading={loading}
            />
            <div className="flex flex-col items-center justify-center w-full h-full">
              <AgentStatusBar
                steps={AGENT_STEPS}
                activeAgents={activeAgents}
                completedAgents={completedAgents}
              />
            </div>
          </div>
        </section>

        {/* System Telemetry & Performance Dashboard */}
        {analytics && (
          <section className="w-full flex justify-center z-10 -mt-2">
            <div className="w-full max-w-6xl border border-pink-500/50 bg-neutral-950/50 backdrop-blur-md rounded-2xl p-4 shadow-[0_0_25px_rgba(212,68,239,0.35)] flex flex-wrap gap-6 items-center justify-around text-neutral-300">
              
              {/* Header Label */}
              <div className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-pink-400 filter drop-shadow-[0_0_8px_rgba(212,68,239,0.3)]" />
                <span className="text-xs uppercase font-extrabold tracking-widest text-neutral-400 font-title">
                  System Analytics
                </span>
              </div>
              
              {/* P50 Latency */}
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400 border border-indigo-500/20">
                  <Clock className="w-4 h-4" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider font-title">P50 Latency</span>
                  <span className="text-sm font-black text-neutral-200">{analytics.p50_latency_sec}s</span>
                </div>
              </div>

              {/* P95 Latency */}
              <div className="flex items-center gap-3">
                <div className="p-2 bg-pink-500/10 rounded-lg text-pink-400 border border-pink-500/20">
                  <Clock className="w-4 h-4 animate-pulse" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider font-title">P95 Latency</span>
                  <span className="text-sm font-black text-neutral-200">{analytics.p95_latency_sec}s</span>
                </div>
              </div>

              {/* Failure Rate */}
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400 border border-emerald-500/20">
                  <AlertOctagon className="w-4 h-4" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider font-title">Failure Rate</span>
                  <span className={`text-sm font-black ${analytics.failure_rate_percent > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                    {analytics.failure_rate_percent}%
                  </span>
                </div>
              </div>

              {/* Avg Tokens/Sec */}
              <div className="flex items-center gap-3">
                <div className="p-2 bg-pink-500/10 rounded-lg text-pink-400 border border-pink-500/20">
                  <Cpu className="w-4 h-4" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider font-title">Avg Speed</span>
                  <span className="text-sm font-black text-neutral-200">{analytics.avg_tokens_per_sec} t/s</span>
                </div>
              </div>

              {/* Total Tokens */}
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400 border border-indigo-500/20">
                  <BarChart3 className="w-4 h-4" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider font-title">Total Tokens</span>
                  <span className="text-sm font-black text-neutral-200">{analytics.total_tokens?.toLocaleString()}</span>
                </div>
              </div>



              {/* Total Requests */}
              <div className="flex items-center gap-3">
                <div className="p-2 bg-neutral-500/10 rounded-lg text-neutral-400 border border-neutral-500/20">
                  <Radio className="w-4 h-4" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider font-title">Total Runs</span>
                  <span className="text-sm font-black text-neutral-200">{analytics.total_requests}</span>
                </div>
              </div>

            </div>
          </section>
        )}

        {/* Contradiction Alert Box */}
        {brief?.contradictions?.length > 0 && (
          <ContradictionAlert contradictions={brief.contradictions} />
        )}

        {/* Analysis Dashboard Workspace Grid */}
        <section className={`grid grid-cols-1 ${brief ? "lg:grid-cols-[1fr_360px]" : "max-w-4xl mx-auto w-full"} gap-8 items-start w-full`}>
          
          {/* Main Content Area - Renders Investment Brief */}
          <div className="flex flex-col gap-6">
            <BriefPanel
              brief={brief}
              loading={loading}
              onCitationClick={setActiveCitation}
            />
          </div>

          {/* Right Metrics & Citations Sidecard */}
          <div className="flex flex-col gap-6 w-full lg:sticky lg:top-4">
            {brief && (
              <ConfidencePanel
                confidence={brief.confidence}
                latencyMs={brief.latency_ms}
              />
            )}
            <CitationPanel
              citations={brief?.citations || []}
              activeCitation={activeCitation}
              onCitationSelect={setActiveCitation}
            />
            {(brief || loading) && (
              <BullishMeter brief={brief} loading={loading} />
            )}
          </div>

        </section>

        {/* Technical Architecture & Criteria interactive guide */}
        <section className="w-full flex justify-center z-10">
          <TechnicalGuide />
        </section>

      </main>
    </div>
  )
}
