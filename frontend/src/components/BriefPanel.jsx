import ReactMarkdown from "react-markdown"
import { TextureCard, TextureCardContent } from "./ui/texture-card"
import { Sparkles, Compass, ShieldAlert, Link, FileText } from "lucide-react"

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
          <p className="text-sm font-semibold text-neutral-400 font-title">
            Agents synthesizing market intelligence...
          </p>
        </TextureCardContent>
      </TextureCard>
    )
  }

  if (!brief) {
    return (
      <div className="w-full flex flex-col gap-6">
        {/* Hero Section */}
        <div className="relative overflow-hidden rounded-3xl border border-white/5 bg-neutral-950/40 backdrop-blur-md p-6 md:p-10 flex flex-col items-center text-center shadow-[0_20px_50px_rgba(0,0,0,0.5)] transform translate-z-0 will-change-transform">
          {/* Decorative glowing gradient sphere in the background */}
          <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-96 h-96 bg-pink-500/10 rounded-full blur-[100px] pointer-events-none" />
          
          <div className="mb-4 p-3 bg-pink-500/10 border border-pink-500/20 text-pink-400 rounded-2xl shadow-[0_0_20px_rgba(212,68,239,0.25)] animate-pulse">
            <Sparkles className="w-8 h-8" />
          </div>

          <h2 className="text-2xl md:text-4xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-pink-400 to-indigo-400 mb-4 uppercase font-title leading-tight">
            SignalScout Intelligence Engine
          </h2>

          <p className="text-base md:text-lg text-neutral-400 max-w-2xl leading-relaxed mb-6">
            A state-of-the-art multi-agent RAG pipeline that extracts, verifies, and synthesizes complex market signals across corporate transcripts, slides, and filings.
          </p>

          <div className="w-24 h-[1px] bg-gradient-to-r from-transparent via-pink-500/50 to-transparent" />
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <TextureCard className="flex-1">
            <TextureCardContent className="p-6 flex flex-col gap-4">
              <div className="w-12 h-12 rounded-2xl bg-pink-500/10 border border-pink-500/30 flex items-center justify-center text-pink-400 shadow-[0_0_15px_rgba(212,68,239,0.1)]">
                <Compass className="w-6 h-6" />
              </div>
              <h4 className="text-lg font-bold text-neutral-200 uppercase tracking-wider font-title">
                Cross-Modal RAG
              </h4>
              <p className="text-sm text-neutral-400 leading-relaxed">
                Queries textual reports, presentation slides, and financial charts simultaneously to build a cohesive narrative.
              </p>
            </TextureCardContent>
          </TextureCard>

          <TextureCard className="flex-1">
            <TextureCardContent className="p-6 flex flex-col gap-4">
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.1)]">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <h4 className="text-lg font-bold text-neutral-200 uppercase tracking-wider font-title">
                Contradiction Check
              </h4>
              <p className="text-sm text-neutral-400 leading-relaxed">
                Automatically checks agent answers against source texts to identify and flag discrepancies or conflicting claims.
              </p>
            </TextureCardContent>
          </TextureCard>

          <TextureCard className="flex-1">
            <TextureCardContent className="p-6 flex flex-col gap-4">
              <div className="w-12 h-12 rounded-2xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400 shadow-[0_0_15px_rgba(168,85,247,0.1)]">
                <Link className="w-6 h-6" />
              </div>
              <h4 className="text-lg font-bold text-neutral-200 uppercase tracking-wider font-title">
                Interactive Citations
              </h4>
              <p className="text-sm text-neutral-400 leading-relaxed">
                Provides clickable deep-linked source tags, letting you inspect the exact audio clip or paragraph behind every metric.
              </p>
            </TextureCardContent>
          </TextureCard>
        </div>
      </div>
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
        <div className="flex items-center gap-2.5">
          <FileText className="text-pink-400 w-5 h-5" />
          <span className="text-xs font-bold text-neutral-400 uppercase tracking-widest font-title">
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
