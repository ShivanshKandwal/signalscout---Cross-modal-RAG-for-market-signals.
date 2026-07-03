import { useState } from "react"
import QueryPanel from "./components/QueryPanel"
import BriefPanel from "./components/BriefPanel"
import CitationPanel from "./components/CitationPanel"
import ConfidencePanel from "./components/ConfidencePanel"
import ContradictionAlert from "./components/ContradictionAlert"
import AgentStatusBar from "./components/AgentStatusBar"
import { GridBeam } from "./components/ui/grid-beam"
import { ShaderGradientCanvas, ShaderGradient } from "shadergradient"

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
    <div className="relative w-full min-h-screen overflow-x-hidden text-neutral-200">
      
      {/* ── 1. Interactive Black-Pink 3D Shader Gradient Canvas ──────────────── */}
      <div className="fixed inset-0 z-0 pointer-events-none select-none opacity-45">
        <ShaderGradientCanvas style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}>
          <ShaderGradient
            control="query"
            urlString="https://www.shadergradient.co/customize?animate=on&axesHelper=off&bgColor1=%23030303&bgColor2=%23030303&brightness=1.1&cAzimuthAngle=180&cDistance=3.5&cPolarAngle=90&cameraZoom=1&color1=%23d444ef&color2=%23030303&color3=%23f472b6&destination=onCanvas&embedMode=off&envMap=off&fog=on&fov=45&frameRate=15&glow=0.2&grain=on&lightType=3d&noiseStrength=3&noiseType=perlin&pixelDensity=1&play=on&positionX=0&positionY=0&positionZ=0&radialDistortion=0.5&range=0.5&rotationX=0&rotationY=0&rotationZ=0&type=water"
          />
        </ShaderGradientCanvas>
        <div className="absolute inset-0 vignette-overlay z-10" />
      </div>

      {/* ── 2. Page Container ────────────────────────────────────────────────── */}
      <div className="relative z-10 flex flex-col md:flex-row min-h-screen w-full">
        
        {/* Left Side Navigation & Controls */}
        <div className="w-full md:w-[350px] md:min-h-screen flex flex-col glass-panel border-r border-white/5 relative shrink-0">
          
          {/* Header & Laser Grid Beam */}
          <div className="w-full h-[180px] shrink-0 border-b border-white/5 bg-neutral-950/20 relative">
            <GridBeam rows={4} cols={5} strength={0.4} duration={5} className="absolute inset-0">
              <div className="w-full h-full flex flex-col justify-end p-5 z-20 relative">
                <div className="flex items-center gap-2 mb-2">
                  <div className="text-xl px-2.5 py-1.5 bg-pink-500/10 border border-pink-500/30 text-pink-400 rounded-xl shadow-[0_0_15px_rgba(212,68,239,0.2)]">
                    📡
                  </div>
                  <span className="text-lg font-bold tracking-tight text-neutral-100 pl-1">
                    SignalScout
                  </span>
                </div>
                <p className="text-[10px] text-neutral-500 font-bold uppercase tracking-widest pl-1">
                  Multimodal Intelligence Agent
                </p>
              </div>
            </GridBeam>
          </div>

          {/* Action Center Panels */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 select-none">
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

            {brief && <ConfidencePanel confidence={brief.confidence} />}
          </div>
        </div>

        {/* Main Brief Workspace Panel */}
        <div className="flex-1 p-4 md:p-8 overflow-y-auto flex flex-col gap-6">
          {/* Contradiction Alert Box */}
          {brief?.contradictions?.length > 0 && (
            <ContradictionAlert contradictions={brief.contradictions} />
          )}

          {/* Brief and Citations Workspace Grid */}
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-6 items-start w-full">
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
        </div>

      </div>
    </div>
  )
}
