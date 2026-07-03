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
      <TextureCard className="w-full min-h-[300px] flex items-center justify-center">
        <TextureCardContent className="flex flex-col items-center justify-center p-8 text-center max-w-md">
          <div className="text-4xl mb-4 text-pink-500 filter drop-shadow-[0_0_15px_rgba(212,68,239,0.4)] animate-pulse">
            📡
          </div>
          <h3 className="text-base font-bold text-neutral-200 mb-2">
            SignalScout Ready
          </h3>
          <p className="text-xs text-neutral-500 leading-relaxed">
            Select an asset, type in your question above, and trigger the multi-agent search graph to generate a report brief.
          </p>
        </TextureCardContent>
      </TextureCard>
    )
  }

  // Helper to highlight key financial metrics and numbers inside text blocks
  const formatTextWithHighlights = (text) => {
    if (typeof text !== "string") return text

    // Parse citation reference tokens
    let parts = text
      .replace(/\[(\d+)\]/g, (match, n) => `__CITE_${n}__`)
      .split("__")

    return parts.map((part, i) => {
      // Check if this part is a citation reference
      const citeMatch = part.match(/^CITE_(\d+)$/)
      if (citeMatch) {
        const idx = parseInt(citeMatch[1]) - 1
        return (
          <span
            key={`cite-${i}`}
            className="citation-ref"
            onClick={() => onCitationClick(idx)}
          >
            {citeMatch[1]}
          </span>
        )
      }

      // Regex to detect financial percentages, margins, or ratios (e.g. 15.5%, +8.4%, -2%)
      const numberRegex = /(\b[+-]?\d+(?:\.\d+)?%|\b[+-]?\d+(?:\.\d+)?\s*(?:basis points|bps)\b|\b\d+\.\d+x\b)/g
      if (numberRegex.test(part)) {
        const subParts = part.split(numberRegex)
        return subParts.map((sub, j) => {
          if (numberRegex.test(sub)) {
            return (
              <strong
                key={`num-${j}`}
                className="font-semibold text-pink-400 font-mono glow-text-pink px-1"
              >
                {sub}
              </strong>
            )
          }
          return sub
        })
      }

      return part
    })
  }

  return (
    <TextureCard className="w-full">
      
      {/* Top Sentiment Highlight Bar */}
      <div
        className={`h-[3px] w-full ${
          brief.sentiment === "bullish"
            ? "bg-gradient-to-r from-emerald-500 to-teal-400"
            : brief.sentiment === "bearish"
            ? "bg-gradient-to-r from-red-500 to-rose-400"
            : "bg-gradient-to-r from-neutral-700 to-neutral-500"
        }`}
      />

      {/* Card Header section */}
      <div className="flex items-center justify-between border-b border-white/5 px-6 py-4 bg-neutral-950/20">
        <div className="flex items-center gap-2">
          <span className="text-pink-400 text-lg">📊</span>
          <span className="text-xs font-bold text-neutral-400 uppercase tracking-widest">
            Investment Brief — {brief.ticker}
          </span>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider ${
            brief.sentiment === "bullish"
              ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.2)]"
              : brief.sentiment === "bearish"
              ? "bg-red-500/10 border border-red-500/30 text-red-400 shadow-[0_0_12px_rgba(239,68,68,0.2)]"
              : "bg-neutral-800/40 border border-white/5 text-neutral-400"
          }`}
        >
          {brief.sentiment}
        </span>
      </div>

      <TextureCardContent className="p-6 md:p-8">
        {/* Markdown Brief Contents */}
        <div className="prose prose-invert max-w-none text-sm leading-relaxed text-neutral-300 space-y-6">
          <ReactMarkdown
            components={{
              h2: ({ children }) => (
                <div className="relative flex items-center mt-8 mb-4 border-b border-white/5 pb-2.5 first:mt-0">
                  {/* Glowing left highlight */}
                  <div className="absolute left-0 w-[3px] h-full bg-gradient-to-b from-pink-500 to-purple-600 rounded-full" />
                  <h2 className="text-sm md:text-base font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-neutral-100 via-pink-300 to-indigo-300 uppercase tracking-wider pl-4">
                    {children}
                  </h2>
                </div>
              ),
              ul: ({ children }) => (
                <ul className="space-y-3.5 text-neutral-300 my-4 pl-1">
                  {children}
                </ul>
              ),
              li: ({ children }) => (
                <li className="flex items-start text-neutral-300 leading-relaxed">
                  {/* Customized glowing pink dot */}
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-500 mt-2 mr-3 shrink-0 shadow-[0_0_8px_rgba(212,68,239,0.7)]" />
                  <div className="flex-1">
                    {React.Children.map(children, child => {
                      if (typeof child === "string") {
                        return formatTextWithHighlights(child)
                      }
                      return child
                    })}
                  </div>
                </li>
              ),
              p: ({ children }) => (
                <p className="text-neutral-300 leading-relaxed my-4 text-justify pl-1">
                  {React.Children.map(children, child => {
                    if (typeof child === "string") {
                      return formatTextWithHighlights(child)
                    }
                    return child
                  })}
                </p>
              ),
            }}
          >
            {brief.brief_markdown}
          </ReactMarkdown>
        </div>
      </TextureCardContent>
    </TextureCard>
  )
}

import React from "react"
