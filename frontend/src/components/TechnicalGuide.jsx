import { useState } from "react"
import { BookOpen, GitMerge, FileCheck, Activity, ChevronRight, HelpCircle } from "lucide-react"

export default function TechnicalGuide() {
  const [activeTab, setActiveTab] = useState("rag")
  const [selectedMetric, setSelectedMetric] = useState("faithfulness")
  const [selectedCriteria, setSelectedCriteria] = useState("failure")

  const metricsInfo = {
    faithfulness: {
      name: "Faithfulness (Primary)",
      formula: "Faithfulness = \\frac{\\text{Claims Grounded in Context}}{\\text{Total Claims in Synthesis}}",
      desc: "Measures whether the generated investment brief is strictly grounded in the retrieved documents and contains zero hallucinations.",
      criteria: "Score of 1.0 (100%) represents absolute alignment. Lower scores indicate claims were synthesized that cannot be verified by any retrieved SEC filing chunk or audio transcript.",
      color: "border-pink-500/30 text-pink-400 bg-pink-500/5",
    },
    relevancy: {
      name: "Answer Relevancy",
      formula: "Relevancy = \\frac{1}{N} \\sum_{i=1}^{N} \\text{CosineSimilarity}(Q, G_i)",
      desc: "Measures whether the generated brief directly addresses the user's initial query without containing redundant or off-topic information.",
      criteria: "Calculated by generating mock questions from the generated brief and comparing them to the original query. High scores mean direct answers.",
      color: "border-rose-500/30 text-rose-400 bg-rose-500/5",
    },
    recall: {
      name: "Context Recall",
      formula: "Recall = \\frac{\\text{Claims in Reference Answer Grounded in Context}}{\\text{Total Claims in Reference Answer}}",
      desc: "Evaluates whether the RAG retrieval step successfully fetched all relevant information required to answer the query.",
      criteria: "Calculated against the consensus gold standard answer. A score of 0% indicates the retrieval mechanism completely missed the relevant filings.",
      color: "border-sky-500/30 text-sky-400 bg-sky-500/5",
    },
    precision: {
      name: "Context Precision",
      formula: "Precision = \\frac{\\text{True Positives Retrieval Chunks}}{\\text{Total Chunks Retrieved}}",
      desc: "Evaluates the signal-to-noise ratio by measuring whether the top-ranked chunks returned by the retriever are truly relevant.",
      criteria: "Calculated by verifying if the most useful chunks are placed at the top of the context window to maximize LLM generation accuracy.",
      color: "border-violet-500/30 text-violet-400 bg-violet-500/5",
    },
  }

  const criteriaInfo = {
    failure: {
      name: "System Failure Rate",
      criteria: "Failed Runs / Total Runs * 100",
      desc: "Triggered if the request encounters an unhandled Python exception, a model provider timeout (Gemini/Groq), or fails to generate a final brief payload.",
      status: "Ideal status is 0%. A failure rate of 0% confirms complete pipeline reliability across all concurrent agent steps.",
    },
    latency: {
      name: "Latency (P50 & P95)",
      criteria: "Sorted percentile arrays of successful request runtimes",
      desc: "P50 represents the median duration (50% of requests finished faster than this). P95 represents the worst-case boundary (only 5% of requests took longer).",
      status: "Measured end-to-end (including multi-modal embedding generation, hybrid RAG query, self-critique agent retries, and SSE connection overhead).",
    },
    tps: {
      name: "Avg Speed (Tokens / Sec)",
      criteria: "Total Generated Tokens / Total Latency (seconds)",
      desc: "Accumulates the input prompt tokens and output completion tokens processed by the Orchestrator, Analysis, and Critique nodes.",
      status: "Averages the cumulative tokens processed per second across all successful brief generations.",
    },
  }

  return (
    <div className="w-full max-w-6xl mt-12 mb-8 border border-pink-500/50 bg-neutral-950/50 backdrop-blur-md rounded-2xl p-6 shadow-[0_0_25px_rgba(212,68,239,0.25)] text-neutral-300">
      
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-white/5 pb-4 mb-6">
        <BookOpen className="w-5 h-5 text-pink-400 filter drop-shadow-[0_0_8px_rgba(212,68,239,0.3)]" />
        <h2 className="text-sm font-black uppercase tracking-widest text-neutral-200 font-title">
          Technical Architecture & Criteria Guide
        </h2>
      </div>

      {/* Tabs Selector */}
      <div className="flex border-b border-white/5 mb-6 gap-2">
        <button
          onClick={() => setActiveTab("rag")}
          className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-all duration-300 flex items-center gap-2 ${
            activeTab === "rag"
              ? "border-pink-500 text-pink-400 bg-pink-500/5"
              : "border-transparent text-neutral-400 hover:text-neutral-200"
          }`}
        >
          <GitMerge className="w-4 h-4" /> RAG Pipeline Flow
        </button>
        <button
          onClick={() => setActiveTab("ragas")}
          className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-all duration-300 flex items-center gap-2 ${
            activeTab === "ragas"
              ? "border-pink-500 text-pink-400 bg-pink-500/5"
              : "border-transparent text-neutral-400 hover:text-neutral-200"
          }`}
        >
          <FileCheck className="w-4 h-4" /> RAGAS Metric Formulas
        </button>
        <button
          onClick={() => setActiveTab("telemetry")}
          className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-all duration-300 flex items-center gap-2 ${
            activeTab === "telemetry"
              ? "border-pink-500 text-pink-400 bg-pink-500/5"
              : "border-transparent text-neutral-400 hover:text-neutral-200"
          }`}
        >
          <Activity className="w-4 h-4" /> Telemetry Criteria
        </button>
      </div>

      {/* Tab 1: RAG Pipeline Flow */}
      {activeTab === "rag" && (
        <div className="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-6 items-start">
          <div className="flex flex-col gap-4">
            <p className="text-sm text-neutral-400 leading-relaxed">
              SignalScout runs a stateful <strong>Multi-Agent RAG pipeline</strong> orchestrated using LangGraph. Each step executes in a sandbox and validates information modality context in sequence:
            </p>
            
            {/* Steps Flow Grid */}
            <div className="grid grid-cols-1 gap-2.5">
              <div className="flex items-start gap-3 bg-neutral-900/30 p-3 rounded-xl border border-white/5">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-pink-500/10 text-pink-400 border border-pink-500/20">01</span>
                <div>
                  <h4 className="text-sm font-bold text-neutral-200">Query Parsing & Intent</h4>
                  <p className="text-xs text-neutral-400">The Orchestrator agent extracts user intent, time ranges, and filters modalities (audio vs documents).</p>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-neutral-900/30 p-3 rounded-xl border border-white/5">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-pink-500/10 text-pink-400 border border-pink-500/20">02</span>
                <div>
                  <h4 className="text-sm font-bold text-neutral-200">Multi-Modal Hybrid Retriever</h4>
                  <p className="text-xs text-neutral-400">Queries database using pgvector semantic dense embeddings (BAAI/bge-m3) and BM25 sparse keyword matching.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-neutral-900/30 p-3 rounded-xl border border-white/5">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-pink-500/10 text-pink-400 border border-pink-500/20">03</span>
                <div>
                  <h4 className="text-sm font-bold text-neutral-200">Context Synthesis & Cross-Check</h4>
                  <p className="text-xs text-neutral-400">Generates the draft brief and matches Management Statement audio transcripts against SEC filings for contradictions.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-neutral-900/30 p-3 rounded-xl border border-white/5">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-pink-500/10 text-pink-400 border border-pink-500/20">04</span>
                <div>
                  <h4 className="text-sm font-bold text-neutral-200">Critique & Self-Correction Retries</h4>
                  <p className="text-xs text-neutral-400">If the quality score does not cross the 0.70 threshold, the Critique agent triggers a feedback loop to re-retrieve.</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-neutral-950/70 p-4 border border-white/5 rounded-xl flex flex-col gap-3">
            <h3 className="text-sm font-bold uppercase text-neutral-400 font-title tracking-wider">Technical Highlights</h3>
            <ul className="text-xs text-neutral-400 flex flex-col gap-2">
              <li className="flex items-center gap-1.5"><ChevronRight className="w-3 h-3 text-pink-400" /> pgvector vector stores</li>
              <li className="flex items-center gap-1.5"><ChevronRight className="w-3 h-3 text-pink-400" /> BAAI/bge-m3 multimodal</li>
              <li className="flex items-center gap-1.5"><ChevronRight className="w-3 h-3 text-pink-400" /> PyTorch NLI models</li>
              <li className="flex items-center gap-1.5"><ChevronRight className="w-3 h-3 text-pink-400" /> Stateful LangGraph loops</li>
            </ul>
          </div>
        </div>
      )}

      {/* Tab 2: RAGAS Metric Formulas */}
      {activeTab === "ragas" && (
        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-6">
          {/* Vertical Menu */}
          <div className="flex flex-col gap-2">
            {Object.keys(metricsInfo).map((key) => (
              <button
                key={key}
                onClick={() => setSelectedMetric(key)}
                className={`w-full text-left px-3 py-2 text-xs font-bold rounded-xl border transition-all duration-300 ${
                  selectedMetric === key
                    ? "border-pink-500/50 bg-pink-500/10 text-pink-400"
                    : "border-white/5 text-neutral-400 hover:text-neutral-200 hover:bg-white/5"
                }`}
              >
                {metricsInfo[key].name}
              </button>
            ))}
          </div>

          {/* Details Panel */}
          <div className="flex flex-col p-4 rounded-xl border border-white/5 bg-neutral-900/10">
            <h3 className="text-sm font-bold text-neutral-200 mb-2">
              {metricsInfo[selectedMetric].name}
            </h3>
            
            {/* LaTeX Equation Style Box */}
            <div className="my-3 p-3 rounded-lg bg-neutral-950 font-mono text-xs border border-white/5 flex items-center justify-center text-center overflow-x-auto text-pink-400">
              {metricsInfo[selectedMetric].formula}
            </div>

            <div className="flex flex-col gap-3.5 mt-2">
              <div>
                <span className="text-[10px] uppercase font-bold text-neutral-500 font-title tracking-wider block">Description</span>
                <p className="text-xs text-neutral-300 leading-relaxed">{metricsInfo[selectedMetric].desc}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-neutral-500 font-title tracking-wider block">Failure/Success Criteria</span>
                <p className="text-xs text-neutral-400 leading-relaxed">{metricsInfo[selectedMetric].criteria}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Telemetry Criteria */}
      {activeTab === "telemetry" && (
        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-6">
          {/* Vertical Menu */}
          <div className="flex flex-col gap-2">
            {Object.keys(criteriaInfo).map((key) => (
              <button
                key={key}
                onClick={() => setSelectedCriteria(key)}
                className={`w-full text-left px-3 py-2 text-xs font-bold rounded-xl border transition-all duration-300 ${
                  selectedCriteria === key
                    ? "border-pink-500/50 bg-pink-500/10 text-pink-400"
                    : "border-white/5 text-neutral-400 hover:text-neutral-200 hover:bg-white/5"
                }`}
              >
                {criteriaInfo[key].name}
              </button>
            ))}
          </div>

          {/* Details Panel */}
          <div className="flex flex-col p-4 rounded-xl border border-white/5 bg-neutral-900/10">
            <h3 className="text-sm font-bold text-neutral-200 mb-2">
              {criteriaInfo[selectedCriteria].name}
            </h3>

            <div className="my-3 p-3 rounded-lg bg-neutral-950 font-mono text-xs border border-white/5 flex items-center justify-center text-pink-400 text-center">
              Formula: {criteriaInfo[selectedCriteria].criteria}
            </div>

            <div className="flex flex-col gap-3.5 mt-2">
              <div>
                <span className="text-[10px] uppercase font-bold text-neutral-500 font-title tracking-wider block">Description</span>
                <p className="text-xs text-neutral-300 leading-relaxed">{criteriaInfo[selectedCriteria].desc}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-neutral-500 font-title tracking-wider block">How it is Measured</span>
                <p className="text-xs text-neutral-400 leading-relaxed">{criteriaInfo[selectedCriteria].status}</p>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
