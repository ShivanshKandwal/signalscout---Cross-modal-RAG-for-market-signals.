import { useState } from "react"
import QueryPanel from "./components/QueryPanel"
import BriefPanel from "./components/BriefPanel"
import CitationPanel from "./components/CitationPanel"
import ConfidencePanel from "./components/ConfidencePanel"
import ContradictionAlert from "./components/ContradictionAlert"
import AgentStatusBar from "./components/AgentStatusBar"
import { GridBeam } from "./components/ui/grid-beam"
import ShaderBackground from "./components/ui/shader-background"

const AGENT_STEPS = [
  { id: "orchestrator", label: "Orchestrator", icon: "🎯" },
  { id: "retrieval",    label: "Retrieval Agent", icon: "🔍" },
  { id: "analysis",     label: "Analysis Agent", icon: "📊" },
  { id: "citation",     label: "Citation Agent", icon: "📎" },
  { id: "contradiction",label: "Contradiction Check", icon: "⚠️" },
  { id: "critique",     label: "Critique Agent", icon: "🧠" },
  { id: "finalize",     label: "Finalize", icon: "✅" },
]

export default function App() {
  const [ticker, setTicker] = useState("AAPL")
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
      const { fetchEventSource } = await import("@microsoft/fetch-event-source")

      await fetchEventSource("/api/brief/stream", {
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
            }
          } catch (e) {
            /* ignore parse errors */
          }
        },

        onerror(err) {
          console.error("SSE error:", err)
          setLoading(false)
        },
      })
    } catch (err) {
      console.error("Request failed:", err)
      setLoading(false)
    }
  }

  return (
    <div className="relative w-full min-h-screen overflow-x-hidden text-neutral-200 bg-black">
      
      {/* ── 1. Real-Time WebGL Fluid Shader Gradient Background (60fps) ────── */}
      <div className="fixed inset-0 z-0 pointer-events-none select-none opacity-40">
        <ShaderBackground />
        <div className="absolute inset-0 vignette-overlay z-10" />
      </div>

      {/* ── 2. Header Grid Header Layout ────────────────────────────────────────── */}
      <header className="relative z-10 w-full border-b border-white/5 bg-neutral-950/40 backdrop-blur-md">
        <GridBeam rows={3} cols={8} strength={0.35} duration={6} className="w-full py-4 px-6 md:px-12">
          <div className="flex items-center justify-between z-20 relative w-full">
            <div className="flex items-center gap-3">
              <div className="text-xl px-2.5 py-1.5 bg-pink-500/10 border border-pink-500/30 text-pink-400 rounded-xl shadow-[0_0_15px_rgba(212,68,239,0.2)]">
                📡
              </div>
              <div>
                <h1 className="text-lg font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-neutral-100 via-pink-400 to-indigo-400">
                  SignalScout
                </h1>
                <p className="text-[9px] text-neutral-500 font-bold uppercase tracking-widest">
                  Cross-Modal RAG Market Analysis Platform
                </p>
              </div>
            </div>
            
            {/* Morphing Dynamic Island Notch */}
            <div className="hidden sm:block shrink-0">
              <AgentStatusBar
                steps={AGENT_STEPS}
                activeAgents={activeAgents}
                completedAgents={completedAgents}
              />
            </div>
          </div>
        </GridBeam>
      </header>

      {/* ── 3. Main Dashboard Workspace Layout ─────────────────────────────── */}
      <main className="relative z-10 max-w-7xl mx-auto px-4 md:px-8 py-8 flex flex-col gap-8">
        
        {/* Mobile Dynamic Island Status Bar */}
        <div className="block sm:hidden w-full">
          <AgentStatusBar
            steps={AGENT_STEPS}
            activeAgents={activeAgents}
            completedAgents={completedAgents}
          />
        </div>

        {/* CENTER STAGE: Huge Prompt search console */}
        <section className="w-full flex justify-center z-20">
          <div className="w-full max-w-4xl">
            <QueryPanel
              ticker={ticker}
              onTickerChange={setTicker}
              onSubmit={handleSubmit}
              loading={loading}
            />
          </div>
        </section>

        {/* Contradiction Alert Box */}
        {brief?.contradictions?.length > 0 && (
          <ContradictionAlert contradictions={brief.contradictions} />
        )}

        {/* Analysis Dashboard Workspace Grid */}
        <section className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8 items-start w-full">
          
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
            {brief && <ConfidencePanel confidence={brief.confidence} />}
            <CitationPanel
              citations={brief?.citations || []}
              activeCitation={activeCitation}
              onCitationSelect={setActiveCitation}
            />
          </div>

        </section>

      </main>
    </div>
  )
}
