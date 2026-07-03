import { cn } from "../lib/utils"
import { AlertTriangle, Mic, FileText } from "lucide-react"

export default function ContradictionAlert({ contradictions }) {
  if (!contradictions?.length) return null

  return (
    <div className="flex flex-col gap-3 w-full mb-6">
      {contradictions.map((c, i) => {
        const isHigh = c.severity === "high"
        return (
          <div
            key={c.id || i}
            className={cn(
              "rounded-2xl border p-4 backdrop-blur-md transition-all duration-300",
              isHigh
                ? "bg-red-500/5 border-red-500/20 active-border-pulse shadow-[0_0_15px_rgba(239,68,68,0.1)]"
                : "bg-amber-500/5 border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.05)]"
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/5 pb-2 mb-3">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className={cn("w-5 h-5", isHigh ? "text-red-400 animate-pulse" : "text-amber-400")} />
                <span className="text-xs font-bold text-neutral-300 uppercase tracking-wider font-title">
                  Cross-Modal Contradiction Detected
                </span>
              </div>
              <span
                className={cn(
                  "px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider font-title",
                  isHigh
                    ? "bg-red-500/15 text-red-400 border border-red-500/20"
                    : "bg-amber-500/15 text-amber-400 border border-amber-500/20"
                )}
              >
                {c.severity} severity
              </span>
            </div>

            {/* Split Claims Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-2">
              <div className="flex flex-col bg-neutral-950/60 border border-white/5 rounded-xl p-3">
                <div className="text-[10px] font-bold text-sky-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5 font-title">
                  <Mic className="w-3.5 h-3.5" /> Management Statement (Audio)
                </div>
                <p className="text-xs text-neutral-300 leading-relaxed italic">
                  "{c.audio_claim}"
                </p>
              </div>

              <div className="flex flex-col bg-neutral-950/60 border border-white/5 rounded-xl p-3">
                <div className="text-[10px] font-bold text-violet-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5 font-title">
                  <FileText className="w-3.5 h-3.5" /> SEC Filing (Document)
                </div>
                <p className="text-xs text-neutral-300 leading-relaxed italic">
                  "{c.document_claim}"
                </p>
              </div>
            </div>

            {/* Footer metrics */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 pt-2 border-t border-white/5 text-[10px] text-neutral-500 font-medium">
              <span>NLI Contradiction Score: {(c.nli_score * 100).toFixed(0)}%</span>
              {c.explanation && (
                <>
                  <span>·</span>
                  <span className="text-neutral-400">{c.explanation}</span>
                </>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
