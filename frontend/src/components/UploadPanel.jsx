import { useState } from "react"
import { Upload, FileText, Music, BarChart2, AlertCircle, CheckCircle } from "lucide-react"

export default function UploadPanel() {
  const [ticker, setTicker] = useState("")
  const [pdfFile, setPdfFile] = useState(null)
  const [audioFile, setAudioFile] = useState(null)
  const [chartFile, setChartFile] = useState(null)
  const [callDate, setCallDate] = useState("")

  const [pdfState, setPdfState] = useState({ status: "idle", message: "" })
  const [audioState, setAudioState] = useState({ status: "idle", message: "" })
  const [chartState, setChartState] = useState({ status: "idle", message: "", caption: null })

  const handleUploadPdf = async () => {
    if (!ticker) {
      setPdfState({ status: "error", message: "Please specify a ticker." })
      return
    }
    if (!pdfFile) {
      setPdfState({ status: "error", message: "Please select a PDF file." })
      return
    }

    setPdfState({ status: "uploading", message: "Extracting and indexing PDF..." })
    const formData = new FormData()
    formData.append("file", pdfFile)
    formData.append("ticker", ticker.toUpperCase())

    try {
      const response = await fetch("http://localhost:8000/api/ingest/pdf", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) throw new Error(await response.text())
      const data = await response.json()
      setPdfState({
        status: "success",
        message: `${data.chunks_stored} chunks indexed for ${ticker.toUpperCase()} — now query this ticker`,
      })
      setPdfFile(null)
    } catch (err) {
      setPdfState({ status: "error", message: err.message || "Failed to upload PDF." })
    }
  }

  const handleUploadAudio = async () => {
    if (!ticker) {
      setAudioState({ status: "error", message: "Please specify a ticker." })
      return
    }
    if (!audioFile) {
      setAudioState({ status: "error", message: "Please select an audio file." })
      return
    }

    setAudioState({ status: "uploading", message: "Uploading audio..." })
    const formData = new FormData()
    formData.append("file", audioFile)
    formData.append("ticker", ticker.toUpperCase())
    if (callDate) {
      formData.append("call_date", callDate)
    }

    try {
      const response = await fetch("http://localhost:8000/api/ingest/audio", {
        method: "POST",
        body: formData,
      })

      if (response.status === 202) {
        setAudioState({
          status: "success",
          message: "Ingestion started: Whisper ASR may take 2-5 min — now query this ticker",
        })
        setAudioFile(null)
      } else {
        throw new Error(await response.text())
      }
    } catch (err) {
      setAudioState({ status: "error", message: err.message || "Failed to upload audio." })
    }
  }

  const handleUploadChart = async () => {
    if (!ticker) {
      setChartState({ status: "error", message: "Please specify a ticker." })
      return
    }
    if (!chartFile) {
      setChartState({ status: "error", message: "Please select a chart image." })
      return
    }

    setChartState({ status: "uploading", message: "Captioning and indexing chart..." })
    const formData = new FormData()
    formData.append("file", chartFile)
    formData.append("ticker", ticker.toUpperCase())

    try {
      const response = await fetch("http://localhost:8000/api/ingest/chart", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) throw new Error(await response.text())
      const data = await response.json()
      setChartState({
        status: "success",
        message: "1 chart chunk indexed successfully!",
        caption: data.caption,
      })
      setChartFile(null)
    } catch (err) {
      setChartState({ status: "error", message: err.message || "Failed to upload chart." })
    }
  }

  return (
    <div className="w-full max-w-6xl mt-8 border border-pink-500/50 bg-neutral-950/50 backdrop-blur-md rounded-2xl p-6 shadow-[0_0_25px_rgba(212,68,239,0.3)] text-neutral-300">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <Upload className="w-5 h-5 text-pink-400 filter drop-shadow-[0_0_8px_rgba(212,68,239,0.3)]" />
          <h2 className="text-sm font-black uppercase tracking-widest text-neutral-200 font-title">
            Multimodal Upload Console
          </h2>
        </div>
        
        {/* Global Ticker Input */}
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-bold uppercase tracking-wider text-neutral-400 font-title">
            Stock Ticker:
          </span>
          <input
            type="text"
            placeholder="e.g. AAPL"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="w-24 px-3 py-1.5 rounded-lg border border-pink-500/30 bg-neutral-950/80 text-xs font-black uppercase tracking-wider text-pink-400 focus:outline-none focus:border-pink-500 text-center font-mono"
          />
        </div>
      </div>

      {/* Grid of upload zones */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Zone 1: PDF */}
        <div className="flex flex-col gap-3 p-4 rounded-xl border border-white/5 bg-neutral-900/10 hover:border-pink-500/20 transition-all duration-300">
          <div className="flex items-center gap-2 border-b border-white/5 pb-2">
            <FileText className="w-4 h-4 text-pink-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-neutral-200 font-title">PDF Document</span>
          </div>
          
          <label className="flex flex-col items-center justify-center border border-dashed border-white/10 rounded-lg p-6 cursor-pointer hover:bg-white/5 transition-all duration-300">
            <Upload className="w-5 h-5 text-neutral-500 mb-2" />
            <span className="text-[10px] text-neutral-400 text-center">
              {pdfFile ? pdfFile.name : "Select or Drop PDF"}
            </span>
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => setPdfFile(e.target.files[0])}
            />
          </label>
          
          {/* Spacer to align height with audio zone */}
          <div className="h-[26px] hidden md:block" />
          
          <button
            onClick={handleUploadPdf}
            disabled={pdfState.status === "uploading"}
            className="w-full bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500/30 hover:border-pink-500 text-pink-400 hover:text-pink-300 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-300"
          >
            {pdfState.status === "uploading" ? "Indexing..." : "Upload PDF"}
          </button>

          {/* Status Message */}
          {pdfState.status !== "idle" && (
            <div className={`mt-2 flex items-start gap-2 p-2.5 rounded-lg text-[11px] ${
              pdfState.status === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
              pdfState.status === "error" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
              "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
            }`}>
              {pdfState.status === "success" && <CheckCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />}
              {pdfState.status === "error" && <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />}
              <span>{pdfState.message}</span>
            </div>
          )}
        </div>

        {/* Zone 2: Audio */}
        <div className="flex flex-col gap-3 p-4 rounded-xl border border-white/5 bg-neutral-900/10 hover:border-pink-500/20 transition-all duration-300">
          <div className="flex items-center gap-2 border-b border-white/5 pb-2">
            <Music className="w-4 h-4 text-pink-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-neutral-200 font-title">Audio File</span>
          </div>

          <label className="flex flex-col items-center justify-center border border-dashed border-white/10 rounded-lg p-6 cursor-pointer hover:bg-white/5 transition-all duration-300">
            <Upload className="w-5 h-5 text-neutral-500 mb-2" />
            <span className="text-[10px] text-neutral-400 text-center">
              {audioFile ? audioFile.name : "Select or Drop Audio (.mp3/.wav/.m4a)"}
            </span>
            <input
              type="file"
              accept=".mp3,.wav,.m4a"
              className="hidden"
              onChange={(e) => setAudioFile(e.target.files[0])}
            />
          </label>
          
          <div className="flex items-center justify-between text-xs">
            <span className="text-neutral-400">Call Date (Optional):</span>
            <input
              type="date"
              value={callDate}
              onChange={(e) => setCallDate(e.target.value)}
              className="px-2 py-1 rounded border border-white/10 bg-neutral-950/80 text-[10px] font-mono text-neutral-300 outline-none focus:border-pink-500/50"
            />
          </div>

          <button
            onClick={handleUploadAudio}
            disabled={audioState.status === "uploading"}
            className="w-full bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500/30 hover:border-pink-500 text-pink-400 hover:text-pink-300 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-300"
          >
            {audioState.status === "uploading" ? "Uploading..." : "Upload Audio"}
          </button>

          {/* Status Message */}
          {audioState.status !== "idle" && (
            <div className={`mt-2 flex items-start gap-2 p-2.5 rounded-lg text-[11px] ${
              audioState.status === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
              audioState.status === "error" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
              "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
            }`}>
              {audioState.status === "success" && <CheckCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />}
              {audioState.status === "error" && <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />}
              <span>{audioState.message}</span>
            </div>
          )}
        </div>

        {/* Zone 3: Chart */}
        <div className="flex flex-col gap-3 p-4 rounded-xl border border-white/5 bg-neutral-900/10 hover:border-pink-500/20 transition-all duration-300">
          <div className="flex items-center gap-2 border-b border-white/5 pb-2">
            <BarChart2 className="w-4 h-4 text-pink-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-neutral-200 font-title">Stock Chart</span>
          </div>

          <label className="flex flex-col items-center justify-center border border-dashed border-white/10 rounded-lg p-6 cursor-pointer hover:bg-white/5 transition-all duration-300">
            <Upload className="w-5 h-5 text-neutral-500 mb-2" />
            <span className="text-[10px] text-neutral-400 text-center">
              {chartFile ? chartFile.name : "Select or Drop Chart Image"}
            </span>
            <input
              type="file"
              accept=".png,.jpg,.jpeg"
              className="hidden"
              onChange={(e) => setChartFile(e.target.files[0])}
            />
          </label>

          {/* Spacer to align height with audio zone */}
          <div className="h-[26px] hidden md:block" />

          <button
            onClick={handleUploadChart}
            disabled={chartState.status === "uploading"}
            className="w-full bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500/30 hover:border-pink-500 text-pink-400 hover:text-pink-300 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-300"
          >
            {chartState.status === "uploading" ? "Captioning..." : "Upload Chart"}
          </button>

          {/* Status Message */}
          {chartState.status !== "idle" && (
            <div className={`mt-2 flex flex-col gap-2 p-2.5 rounded-lg text-[11px] ${
              chartState.status === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
              chartState.status === "error" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
              "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
            }`}>
              <div className="flex items-start gap-2">
                {chartState.status === "success" && <CheckCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />}
                {chartState.status === "error" && <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />}
                <span>{chartState.message}</span>
              </div>
              
              {/* Show chart technical summary caption on success */}
              {chartState.status === "success" && chartState.caption?.technical_summary && (
                <div className="mt-1.5 p-2 rounded bg-neutral-950/80 border border-emerald-500/10 text-[10px] text-neutral-300 italic leading-relaxed">
                  <strong>VLM Summary:</strong> "{chartState.caption.technical_summary}"
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
