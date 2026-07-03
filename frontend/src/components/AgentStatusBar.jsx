import { Target, Search, BarChart3, Link2, AlertTriangle, Brain, CheckCircle2, Cpu } from "lucide-react"

const ICON_MAP = {
  Target: Target,
  Search: Search,
  BarChart3: BarChart3,
  Link2: Link2,
  AlertTriangle: AlertTriangle,
  Brain: Brain,
  CheckCircle2: CheckCircle2,
}

export default function AgentStatusBar({ steps, activeAgents, completedAgents }) {
  const activeStep = steps.find(s => activeAgents.includes(s.id))
  const isRunning = activeAgents.length > 0

  return (
    <div className="flex flex-col items-center justify-center py-4 w-full h-full">
      <div className="relative flex flex-col w-full max-w-[320px] min-h-[360px] p-5 rounded-2xl border border-pink-500/50 shadow-[0_0_25px_rgba(212,68,239,0.35)] bg-neutral-950/50 backdrop-blur-md justify-between">
        
        {/* Top Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2">
            <Cpu className="w-4.5 h-4.5 text-pink-400 animate-pulse" />
            <span className="text-xs font-black uppercase tracking-widest text-pink-400 font-title">
              {isRunning ? "Pipeline Active" : "Pipeline Standby"}
            </span>
          </div>
          <span className="text-xs font-bold text-neutral-400 font-mono">
            {isRunning ? `${completedAgents.length + 1} / ${steps.length}` : "Idle"}
          </span>
        </div>

        {/* Steps List */}
        <div className="flex flex-col gap-2.5 my-4">
          {steps.map((step) => {
            const isActive = activeAgents.includes(step.id)
            const isComplete = completedAgents.includes(step.id)
            const StepIcon = ICON_MAP[step.icon] || Cpu
            
            return (
              <div 
                key={step.id} 
                className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-all duration-300 ${
                  isActive 
                    ? "bg-pink-500/10 border border-pink-500/30 text-pink-400" 
                    : isComplete 
                    ? "text-emerald-400" 
                    : "text-neutral-500"
                }`}
              >
                <div className={`p-1.5 rounded-lg ${isActive ? "bg-pink-500/20" : isComplete ? "bg-emerald-500/10" : "bg-white/5"}`}>
                  <StepIcon className="w-4 h-4" />
                </div>
                <span className="text-sm font-bold font-title tracking-wide">{step.label}</span>
                
                {/* Right status marker */}
                <div className="ml-auto">
                  {isActive ? (
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-pink-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-pink-500"></span>
                    </span>
                  ) : isComplete ? (
                    <span className="text-xs font-black text-emerald-400 font-mono">✓</span>
                  ) : (
                    <span className="text-[10px] font-bold text-neutral-700 font-mono">○</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Bottom Status Summary */}
        <div className="border-t border-white/5 pt-3 flex items-center justify-between text-xs text-neutral-400">
          <span>Active Agent:</span>
          <span className="font-bold text-neutral-200">
            {isRunning ? activeStep?.label : "None"}
          </span>
        </div>

      </div>
    </div>
  )
}
