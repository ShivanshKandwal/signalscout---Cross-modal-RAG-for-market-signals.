import { motion, AnimatePresence } from "framer-motion"
import { Target, Search, BarChart3, Link2, AlertTriangle, Brain, CheckCircle2, Activity, Cpu } from "lucide-react"

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
  const IconComponent = activeStep ? (ICON_MAP[activeStep.icon] || Cpu) : Cpu

  return (
    <div className="flex flex-col items-center justify-center py-4 w-full">
      {/* Floating Dynamic Island Container */}
      <motion.div
        layout
        initial={{ borderRadius: 24, width: "180px" }}
        animate={{
          width: isRunning ? "300px" : "200px",
          height: isRunning ? "auto" : "44px",
          borderRadius: 24,
        }}
        transition={{ type: "spring", stiffness: 180, damping: 20 }}
        className="glass-panel relative flex flex-col items-center justify-center px-4 overflow-hidden border border-white/10 shadow-[0_0_20px_rgba(212,68,239,0.15)] bg-neutral-950/80"
      >
        <AnimatePresence mode="wait">
          {!isRunning ? (
            <motion.div
              key="idle"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-2.5 h-full text-sm font-bold tracking-wide text-neutral-300 select-none py-2 font-title"
            >
              <Activity className="w-4 h-4 text-emerald-500 animate-pulse" />
              <span>Pipeline Idle</span>
            </motion.div>
          ) : (
            <motion.div
              key="active"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full py-3.5 flex flex-col items-center"
            >
              {/* Dynamic Island Header Indicator */}
              <div className="flex items-center justify-between w-full border-b border-white/5 pb-2 mb-2.5">
                <span className="text-[11px] font-bold uppercase tracking-widest text-pink-400 animate-pulse font-title">
                  Agent Active
                </span>
                <span className="text-[10px] font-bold text-neutral-400 font-title">
                  {completedAgents.length + 1} of {steps.length}
                </span>
              </div>

              {/* Dynamic Active Agent Display */}
              <div className="flex items-center gap-3.5 w-full pl-2">
                <motion.div
                  animate={{ scale: [1, 1.15, 1] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                >
                  <IconComponent className="w-6 h-6 text-pink-400 filter drop-shadow-[0_0_8px_rgba(212,68,239,0.5)]" />
                </motion.div>
                <div className="flex flex-col items-start">
                  <span className="text-base font-bold text-neutral-200 font-title">
                    {activeStep?.label || "Processing"}
                  </span>
                  <span className="text-xs text-neutral-500">
                    Executing logic node...
                  </span>
                </div>
              </div>

              {/* Steps Progress Indicators */}
              <div className="flex items-center justify-center gap-1.5 w-full mt-3">
                {steps.map((step) => {
                  const isActive = activeAgents.includes(step.id)
                  const isComplete = completedAgents.includes(step.id)
                  return (
                    <div
                      key={step.id}
                      title={step.label}
                      className={`h-1.5 rounded-full transition-all duration-300 ${
                        isActive
                          ? "w-8 bg-pink-500 animate-pulse"
                          : isComplete
                          ? "w-4 bg-emerald-500"
                          : "w-2 bg-neutral-800"
                      }`}
                    />
                  )
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
