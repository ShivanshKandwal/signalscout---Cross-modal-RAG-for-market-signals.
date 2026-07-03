import { useState, useRef } from "react"
import { TextureCard, TextureCardContent } from "./ui/texture-card"
import { TextureButton } from "./ui/texture-button"
import { Sparkles, Search, FileText, Music, BarChart2, CheckCircle2, AlertCircle } from "lucide-react"

const TICKERS = [
  { symbol: "AAPL", name: "Apple" },
  { symbol: "MSFT", name: "Microsoft" },
  { symbol: "GOOGL", name: "Google" },
  { symbol: "NVDA", name: "Nvidia" },
  { symbol: "TSLA", name: "Tesla" },
  { symbol: "AMZN", name: "Amazon" },
  { symbol: "META", name: "Meta" },
  { symbol: "JPM", name: "JPMorgan" }
]

const SAMPLE_QUERIES = [
  "What are the main supply chain risks?",
  "What did management say about Q3 growth?",
  "Summarize recent earnings call sentiment",
  "What is the current technical trend?",
]

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

export default function QueryPanel({ ticker, onTickerChange, onSubmit, loading }) {
  const [query, setQuery] = useState("")
  const [pendingFile, setPendingFile] = useState(null) // { type, name, file }
  const [uploadStatus, setUploadStatus] = useState({ state: "idle", message: "" })
  const [isUploading, setIsUploading] = useState(false)

  const pdfInputRef = useRef(null)
  const audioInputRef = useRef(null)
  const chartInputRef = useRef(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!query.trim() || loading || isUploading) return

    if (pendingFile) {
      if (!ticker) {
        setUploadStatus({ state: "error", message: "Please select an asset ticker first." })
        return
      }

      setIsUploading(true)
      setUploadStatus({ state: "loading", message: `Uploading ${pendingFile.type.toUpperCase()} file...` })
      const formData = new FormData()
      formData.append("file", pendingFile.file)
      formData.append("ticker", ticker)

      try {
        const response = await fetch(`${API_URL}/api/ingest/${pendingFile.type}`, {
          method: "POST",
          body: formData,
        })

        if (response.status === 202 || response.ok) {
          let msg = ""
          if (pendingFile.type === "pdf") {
            const data = await response.json()
            msg = `Indexed ${data.chunks_stored} chunks for ${ticker}.`
          } else if (pendingFile.type === "audio") {
            msg = `Started Whisper ASR for ${ticker} (takes 2-5 min).`
          } else {
            msg = `Indexed chart indicators for ${ticker}.`
          }
          setUploadStatus({ state: "success", message: msg })
          setPendingFile(null)
        } else {
          throw new Error(await response.text())
        }
      } catch (err) {
        setUploadStatus({ state: "error", message: err.message || "Ingestion failed." })
        setIsUploading(false)
        return
      }
      setIsUploading(false)
    }

    onSubmit(query.trim())
  }

  const handleFileSelect = (type, e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPendingFile({ type, name: file.name, file })
    setUploadStatus({ state: "idle", message: "" })
  }

  return (
    <TextureCard className="w-full">
      <TextureCardContent className="flex flex-col gap-8 p-8">
        {/* Ticker Section */}
        <div>
          <p className="text-sm font-bold text-neutral-300 uppercase tracking-widest mb-4 pl-1 font-title">
            Select Asset Ticker
          </p>
          <div className="grid grid-cols-4 gap-3.5">
            {TICKERS.map((t) => {
              const isActive = ticker === t.symbol
              return (
                <button
                  key={t.symbol}
                  onClick={() => onTickerChange(t.symbol)}
                  className={`py-4 text-base font-extrabold rounded-xl transition-all duration-200 border cursor-pointer font-title ${
                    isActive
                      ? "bg-pink-500/10 border-pink-500/40 text-pink-400 shadow-[0_0_15px_rgba(212,68,239,0.25)] scale-[1.02]"
                      : "bg-neutral-900/40 border-white/5 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900 hover:scale-[1.01]"
                  }`}
                >
                  {t.name}
                </button>
              )
            })}
          </div>
        </div>

        {/* Query Input Section */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <div className="flex flex-col relative">
            <p className="text-sm font-bold text-neutral-300 uppercase tracking-widest mb-4 pl-1 font-title flex items-center justify-between">
              <span>Query Multi-Agent Research System</span>
              <span className="text-[10px] text-pink-400 font-mono tracking-normal uppercase">
                {ticker ? `Active Stock: ${ticker}` : "No Asset Selected"}
              </span>
            </p>
            
            <div className="relative">
              <textarea
                className="w-full bg-white/5 backdrop-blur-xl border border-white/15 focus:border-pink-500/40 rounded-2xl pl-6 pr-32 py-4 text-lg text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-pink-500/20 transition-all resize-none shadow-inner min-h-[90px]"
                placeholder="Ask about earnings calls, SEC risks, sentiment, stock charts..."
                rows={3}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit(e)
                }}
              />

              {/* Multimodal Quick Attachments Tray */}
              <div className="absolute bottom-3 right-4 flex items-center gap-3 bg-neutral-950/80 backdrop-blur border border-white/10 py-1.5 px-3 rounded-full shadow-lg">
                <input
                  type="file"
                  accept=".pdf"
                  ref={pdfInputRef}
                  onChange={(e) => handleFileSelect("pdf", e)}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => pdfInputRef.current?.click()}
                  title="Attach PDF"
                  className="text-neutral-400 hover:text-pink-400 transition-colors duration-200 cursor-pointer"
                >
                  <FileText className="w-4 h-4" />
                </button>

                <input
                  type="file"
                  accept=".mp3,.wav,.m4a"
                  ref={audioInputRef}
                  onChange={(e) => handleFileSelect("audio", e)}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => audioInputRef.current?.click()}
                  title="Attach Audio (.mp3/.wav/.m4a)"
                  className="text-neutral-400 hover:text-pink-400 transition-colors duration-200 cursor-pointer"
                >
                  <Music className="w-4 h-4" />
                </button>

                <input
                  type="file"
                  accept=".png,.jpg,.jpeg"
                  ref={chartInputRef}
                  onChange={(e) => handleFileSelect("chart", e)}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => chartInputRef.current?.click()}
                  title="Attach Chart Image"
                  className="text-neutral-400 hover:text-pink-400 transition-colors duration-200 cursor-pointer"
                >
                  <BarChart2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Pending File Preview Pill */}
            {pendingFile && (
              <div className="flex items-center gap-2 mt-2 px-3 py-1.5 rounded-lg border border-pink-500/30 bg-neutral-950/80 text-xs w-fit text-neutral-300">
                <FileText className="w-3.5 h-3.5 text-pink-400" />
                <span className="truncate max-w-[200px] font-mono">{pendingFile.name}</span>
                <button
                  type="button"
                  onClick={() => setPendingFile(null)}
                  className="text-neutral-500 hover:text-rose-400 font-bold ml-1.5 transition-colors cursor-pointer"
                >
                  ✕
                </button>
              </div>
            )}
          </div>

          {/* Quick upload status display */}
          {uploadStatus.state !== "idle" && (
            <div className={`flex items-center gap-2 p-2.5 rounded-lg text-xs ${
              uploadStatus.state === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
              uploadStatus.state === "error" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
              "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse"
            }`}>
              {uploadStatus.state === "success" && <CheckCircle2 className="w-4 h-4 shrink-0" />}
              {uploadStatus.state === "error" && <AlertCircle className="w-4 h-4 shrink-0" />}
              {uploadStatus.state === "loading" && <span className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin shrink-0" />}
              <span>{uploadStatus.message}</span>
            </div>
          )}

          {/* Sample Queries */}
          <div className="flex flex-col gap-3 pl-1">
            {SAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQuery(q)}
                className="text-left text-neutral-400 hover:text-pink-400 text-base transition-colors cursor-pointer truncate py-1"
              >
                ↳ {q}
              </button>
            ))}
          </div>

          {/* Submit Button */}
          <TextureButton
            type="submit"
            variant="accent"
            size="lg"
            disabled={loading || !query.trim()}
            className="w-full text-base font-black tracking-widest uppercase font-title cursor-pointer shadow-lg disabled:opacity-50 disabled:bg-pink-900"
          >
            {loading ? (
              <div className="flex items-center justify-center gap-3">
                <span className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Synthesizing Market Data...</span>
              </div>
            ) : (
              <div className="flex items-center justify-center gap-3">
                <Sparkles className="w-6 h-6" />
                <span>Generate Intelligence Brief</span>
              </div>
            )}
          </TextureButton>
        </form>
      </TextureCardContent>
    </TextureCard>
  )
}
