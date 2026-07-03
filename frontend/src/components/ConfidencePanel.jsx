import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from "recharts"
import { TextureCard, TextureCardContent } from "./ui/texture-card"
import { AnimatedNumber } from "./ui/animated-number"
import { ShieldCheck, Zap } from "lucide-react"

const METRIC_COLORS = {
  faithfulness: "#d444ef",       // Pink/purple
  answer_relevancy: "#f472b6",   // Light pink
  context_recall: "#38bdf8",     // Blue
  context_precision: "#a78bfa",  // Lavender
}

export default function ConfidencePanel({ confidence, latencyMs }) {
  if (!confidence) return null

  const metrics = [
    { label: "Faithfulness", key: "faithfulness" },
    { label: "Relevancy", key: "answer_relevancy" },
    { label: "Recall", key: "context_recall" },
    { label: "Precision", key: "context_precision" },
  ]

  const radarData = metrics.map((m) => ({
    metric: m.label,
    score: Math.round((confidence[m.key] || 0) * 100),
    fullMark: 100,
  }))

  const overall = confidence.overall || 0

  return (
    <TextureCard className="w-full">
      <TextureCardContent className="flex flex-col p-5 gap-4">
        {/* Header with animated Overall Score */}
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="text-pink-400 w-5 h-5" />
            <span className="text-xs font-bold text-neutral-400 uppercase tracking-widest font-title">
              Confidence Score
            </span>
          </div>
          <div className="text-xl font-bold font-mono text-pink-400 pl-2 font-title">
            <AnimatedNumber
              value={Math.round(overall * 100)}
              format={(n) => `${n}%`}
            />
          </div>
        </div>

        {/* Radar Chart Visual */}
        <div className="relative w-full h-[180px] flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <defs>
                <radialGradient id="radar-glow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#d444ef" stopOpacity={0.45} />
                  <stop offset="60%" stopColor="#d444ef" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#d444ef" stopOpacity={0.0} />
                </radialGradient>
                <filter id="radar-glow-filter" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <PolarGrid stroke="rgba(255,255,255,0.04)" />
              <PolarAngleAxis
                dataKey="metric"
                tick={{ fill: "#a1a1aa", fontSize: 9, fontWeight: 600 }}
              />
              <Radar
                name="Score"
                dataKey="score"
                stroke="#d444ef"
                fill="url(#radar-glow)"
                fillOpacity={0.8}
                strokeWidth={2}
                filter="url(#radar-glow-filter)"
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(9, 9, 11, 0.95)",
                  border: "1px solid rgba(212,68,239,0.3)",
                  borderRadius: "10px",
                  fontSize: "11px",
                  color: "#fafafa",
                  boxShadow: "0 0 15px rgba(212,68,239,0.2)",
                }}
                formatter={(val) => [`${val}%`, ""]}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Metrics Grid */}
        <div className="flex flex-col gap-3">
          {metrics.map((m) => {
            const val = confidence[m.key] || 0
            const color = METRIC_COLORS[m.key]
            return (
              <div key={m.key} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-neutral-400 font-medium">{m.label}</span>
                  <span className="font-mono font-bold" style={{ color }}>
                    <AnimatedNumber
                      value={Math.round(val * 100)}
                      format={(n) => `${n}%`}
                    />
                  </span>
                </div>
                {/* Custom Neumorphic Progress track */}
                <div className="w-full h-1.5 bg-neutral-950/80 rounded-full overflow-hidden border border-white/[0.02]">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{
                      width: `${val * 100}%`,
                      background: `linear-gradient(90deg, ${color}cc, ${color})`,
                      boxShadow: `0 0 10px ${color}55`,
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>

        {/* Latency request telemetry */}
        {latencyMs !== undefined && (
          <div className="flex items-center justify-between border-t border-white/5 pt-3.5 mt-2 text-xs text-neutral-400 font-medium">
            <div className="flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-indigo-400" />
              <span>Latency: <strong className="text-neutral-300 font-mono">{(latencyMs / 1000).toFixed(2)}s</strong></span>
            </div>
          </div>
        )}
      </TextureCardContent>
    </TextureCard>
  )
}
