import { useState } from "react"
import { TextureCard, TextureCardContent } from "./ui/texture-card"
import { TextureButton } from "./ui/texture-button"

const TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "AMZN", "META", "JPM"]

const SAMPLE_QUERIES = [
  "What are the main supply chain risks?",
  "What did management say about Q3 growth?",
  "Summarize recent earnings call sentiment",
  "What is the current technical trend?",
]

export default function QueryPanel({ ticker, onTickerChange, onSubmit, loading }) {
  const [query, setQuery] = useState("")

  function handleSubmit(e) {
    e.preventDefault()
    if (query.trim() && !loading) onSubmit(query.trim())
  }

  return (
    <TextureCard className="w-full">
      <TextureCardContent className="flex flex-col gap-6 p-5">
        {/* Ticker Section */}
        <div>
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-3 pl-1">
            Select Asset
          </p>
          <div className="grid grid-cols-4 gap-2">
            {TICKERS.map((t) => {
              const isActive = ticker === t
              return (
                <button
                  key={t}
                  onClick={() => onTickerChange(t)}
                  className={`py-2 text-xs font-semibold rounded-lg transition-all duration-200 border cursor-pointer ${
                    isActive
                      ? "bg-pink-500/10 border-pink-500/40 text-pink-400 shadow-[0_0_12px_rgba(212,68,239,0.15)]"
                      : "bg-neutral-900/40 border-white/5 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900"
                  }`}
                >
                  {t}
                </button>
              )
            })}
          </div>
        </div>

        {/* Query Input Section */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col">
            <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-3 pl-1">
              Ask Research Agent
            </p>
            <textarea
              className="w-full bg-neutral-950/80 border border-white/5 focus:border-pink-500/40 rounded-xl px-4 py-3 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-pink-500/30 transition-all resize-none shadow-inner"
              placeholder="Ask about earnings calls, SEC risks, sentiment, stock charts..."
              rows={4}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit(e)
              }}
            />
          </div>

          {/* Sample Queries */}
          <div className="flex flex-col gap-1.5 pl-1">
            {SAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQuery(q)}
                className="text-left text-neutral-500 hover:text-pink-400 text-xs transition-colors cursor-pointer truncate py-0.5"
              >
                ↳ {q}
              </button>
            ))}
          </div>

          {/* Submit Button */}
          <TextureButton
            type="submit"
            variant="accent"
            size="default"
            disabled={loading || !query.trim()}
          >
            {loading ? (
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Analyzing Signals...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span>📡</span>
                <span>Generate Brief</span>
              </div>
            )}
          </TextureButton>
        </form>
      </TextureCardContent>
    </TextureCard>
  )
}
