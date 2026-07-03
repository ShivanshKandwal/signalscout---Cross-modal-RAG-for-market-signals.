import { useEffect, useState } from "react"

export default function BullishMeter({ brief, loading }) {
  const [needleAngle, setNeedleAngle] = useState(-90)

  const sentiment = brief?.sentiment || "neutral"
  const overall = brief?.confidence?.overall || 0.0
  const faithfulness = brief?.confidence?.faithfulness || 0.0
  const relevancy = brief?.confidence?.answer_relevancy || 0.0
  const recall = brief?.confidence?.context_recall || 0.0

  useEffect(() => {
    if (loading) {
      setNeedleAngle(-90)
      return
    }

    let value = 0.5
    if (sentiment === "bearish") {
      value = 0.5 - overall * 0.5
    } else if (sentiment === "bullish") {
      value = 0.5 + overall * 0.5
    } else {
      value = 0.5
    }

    const targetAngle = -90 + value * 180
    // Trigger transition delay slightly to ensure DOM is rendered
    const timer = setTimeout(() => {
      setNeedleAngle(targetAngle)
    }, 150)

    return () => clearTimeout(timer)
  }, [sentiment, overall, loading])

  if (loading) {
    return (
      <div className="w-full border border-pink-500/20 bg-neutral-950/50 backdrop-blur-md rounded-2xl p-5 shadow-[0_0_25px_rgba(212,68,239,0.2)] animate-pulse flex flex-col items-center gap-4">
        <div className="w-full flex justify-between border-b border-white/5 pb-2">
          <div className="h-4 w-24 bg-neutral-800 rounded" />
        </div>
        <div className="w-40 h-20 bg-neutral-800 rounded-t-full mt-4" />
        <div className="h-6 w-32 bg-neutral-800 rounded" />
        <div className="h-4 w-20 bg-neutral-800 rounded" />
        <div className="flex gap-2 w-full justify-center">
          <div className="h-6 w-16 bg-neutral-800 rounded-full" />
          <div className="h-6 w-16 bg-neutral-800 rounded-full" />
          <div className="h-6 w-16 bg-neutral-800 rounded-full" />
        </div>
      </div>
    )
  }

  if (!brief) return null

  const sentimentColor =
    sentiment === "bullish" ? "text-emerald-400" :
    sentiment === "bearish" ? "text-rose-400" :
    "text-amber-400"

  const strokeColor =
    sentiment === "bullish" ? "#22c55e" :
    sentiment === "bearish" ? "#ef4444" :
    "#f59e0b"

  return (
    <div className="w-full border border-pink-500/50 bg-[#0d1117]/80 backdrop-blur-md rounded-2xl p-5 shadow-[0_0_25px_rgba(212,68,239,0.3)] flex flex-col items-center gap-4">
      {/* Title */}
      <div className="w-full border-b border-white/5 pb-2 flex justify-between items-center">
        <span className="text-[10px] font-black uppercase tracking-widest text-pink-400 font-title">
          Signal Strength
        </span>
      </div>

      {/* Semicircle SVG Gauge */}
      <div className="relative w-48 h-24 mt-4 overflow-hidden flex items-end justify-center">
        <svg viewBox="0 0 200 100" className="w-full h-full">
          <defs>
            {/* Red / Bearish Gradient */}
            <linearGradient id="bearish-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0.6} />
            </linearGradient>
            {/* Amber / Neutral Gradient */}
            <linearGradient id="neutral-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.6} />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
            {/* Green / Bullish Gradient */}
            <linearGradient id="bullish-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#22c55e" stopOpacity={0.6} />
              <stop offset="100%" stopColor="#22c55e" />
            </linearGradient>
            {/* Needle Glow */}
            <filter id="needle-glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Semicircle Arc Track - Bearish (Left Third) */}
          <path
            d="M 20 100 A 80 80 0 0 1 80 20"
            fill="none"
            stroke="url(#bearish-grad)"
            strokeWidth="12"
            strokeLinecap="round"
          />

          {/* Semicircle Arc Track - Neutral (Middle Third) */}
          <path
            d="M 80 20 A 80 80 0 0 1 120 20"
            fill="none"
            stroke="#f59e0b"
            strokeWidth="12"
          />

          {/* Semicircle Arc Track - Bullish (Right Third) */}
          <path
            d="M 120 20 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="url(#bullish-grad)"
            strokeWidth="12"
            strokeLinecap="round"
          />

          {/* Needle Group */}
          <g
            transform={`translate(100, 100) rotate(${needleAngle})`}
            style={{ transition: "transform 800ms cubic-bezier(0.25, 0.8, 0.25, 1)" }}
          >
            {/* Thin Needle line */}
            <line
              x1="0"
              y1="0"
              x2="0"
              y2="-85"
              stroke="#ffffff"
              strokeWidth="2.5"
            />
            {/* Needle glowing tip */}
            <circle
              cx="0"
              cy="-85"
              r="4.5"
              fill={strokeColor}
              filter="url(#needle-glow)"
            />
          </g>

          {/* Core Cap */}
          <circle cx="100" cy="100" r="10" fill="#0d1117" stroke="#ffffff" strokeWidth="2" />
        </svg>
      </div>

      {/* Sentiment labels and details */}
      <div className="flex flex-col items-center gap-1">
        <span className={`text-lg font-black uppercase tracking-wider font-title ${sentimentColor}`}>
          {sentiment}
        </span>
        <span className="text-xs text-neutral-400 font-medium">
          {Math.round(overall * 100)}% confidence
        </span>
      </div>

      {/* Metrics pills row */}
      <div className="flex flex-wrap gap-2 w-full justify-center mt-2">
        <div className="px-2.5 py-1 rounded-full border border-pink-500/20 bg-neutral-950/80 text-[10px] text-pink-400 font-mono flex items-center gap-1 shadow-inner">
          <span className="text-neutral-500">Faithfulness:</span>
          <strong>{Math.round(faithfulness * 100)}%</strong>
        </div>
        <div className="px-2.5 py-1 rounded-full border border-pink-500/20 bg-neutral-950/80 text-[10px] text-pink-400 font-mono flex items-center gap-1 shadow-inner">
          <span className="text-neutral-500">Relevancy:</span>
          <strong>{Math.round(relevancy * 100)}%</strong>
        </div>
        <div className="px-2.5 py-1 rounded-full border border-pink-500/20 bg-neutral-950/80 text-[10px] text-pink-400 font-mono flex items-center gap-1 shadow-inner">
          <span className="text-neutral-500">Recall:</span>
          <strong>{Math.round(recall * 100)}%</strong>
        </div>
      </div>
    </div>
  )
}
