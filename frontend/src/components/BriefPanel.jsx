import ReactMarkdown from "react-markdown"
import { TextureCard, TextureCardContent } from "./ui/texture-card"

export default function BriefPanel({ brief, loading, onCitationClick }) {
  if (loading && !brief) {
    return (
      <TextureCard className="w-full min-h-[400px] flex items-center justify-center">
        <TextureCardContent className="flex flex-col items-center justify-center p-8 gap-4">
          <div className="flex gap-2">
            <span className="w-2.5 h-2.5 bg-pink-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
            <span className="w-2.5 h-2.5 bg-pink-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
            <span className="w-2.5 h-2.5 bg-pink-500 rounded-full animate-bounce" />
          </div>
          <p className="text-sm font-semibold text-neutral-400">
            Agents synthesizing market intelligence...
          </p>
        </TextureCardContent>
      </TextureCard>
    )
  }

  if (!brief) {
    return (
      <TextureCard className="w-full min-h-[400px] flex items-center justify-center">
        <TextureCardContent className="flex flex-col items-center justify-center p-8 text-center max-w-sm">
          <div className="text-4xl mb-4 text-pink-500 filter drop-shadow-[0_0_15px_rgba(212,68,239,0.4)] animate-pulse">
            📡
          </div>
          <h3 className="text-base font-bold text-neutral-200 mb-2">
            System Operational
          </h3>
          <p className="text-xs text-neutral-500 leading-relaxed">
            Select a ticker asset, input your query prompt, and click Generate Brief to trigger the multi-agent search graph.
          </p>
        </TextureCardContent>
      </TextureCard>
    )
  }

  return (
    <TextureCard className="w-full">
      {/* Card Header section */}
      <div className="flex items-center justify-between border-b border-white/5 px-6 py-4">
        <div className="flex items-center gap-2">
          <span className="text-pink-400">📋</span>
          <span className="text-xs font-bold text-neutral-400 uppercase tracking-widest">
            Investment Brief — {brief.ticker}
          </span>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
            brief.sentiment === "bullish"
              ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.15)]"
              : brief.sentiment === "bearish"
              ? "bg-red-500/10 border border-red-500/30 text-red-400 shadow-[0_0_10px_rgba(239,68,68,0.15)]"
              : "bg-neutral-800/40 border border-white/5 text-neutral-400"
          }`}
        >
          {brief.sentiment}
        </span>
      </div>

      <TextureCardContent className="p-6">
        {/* Markdown Brief Contents */}
        <div className="prose prose-invert max-w-none text-sm leading-relaxed text-neutral-300 space-y-4">
          <ReactMarkdown
            components={{
              h2: ({ children }) => (
                <h2 className="text-base font-bold text-neutral-100 border-b border-white/5 pb-2 mt-6 mb-3 first:mt-0 uppercase tracking-wide">
                  {children}
                </h2>
              ),
              ul: ({ children }) => (
                <ul className="list-disc pl-5 space-y-2 text-neutral-300 my-3">
                  {children}
                </ul>
              ),
              li: ({ children }) => (
                <li className="text-neutral-300">
                  {children}
                </li>
              ),
              p: ({ children }) => (
                <p className="text-neutral-300 leading-relaxed my-3">
                  {children}
                </p>
              ),
              // Convert [N] citation refs to clickable inline badges
              text: ({ children }) => {
                if (typeof children !== "string") return <>{children}</>
                return children
                  .replace(/\[(\d+)\]/g, (match, n) => `__CITE_${n}__`)
                  .split("__")
                  .map((part, i) => {
                    const citeMatch = part.match(/^CITE_(\d+)$/)
                    if (citeMatch) {
                      const idx = parseInt(citeMatch[1]) - 1
                      return (
                        <span
                          key={i}
                          className="citation-ref"
                          onClick={() => onCitationClick(idx)}
                        >
                          {citeMatch[1]}
                        </span>
                      )
                    }
                    return part
                  })
              },
            }}
          >
            {brief.brief_markdown}
          </ReactMarkdown>
        </div>
      </TextureCardContent>
    </TextureCard>
  )
}
