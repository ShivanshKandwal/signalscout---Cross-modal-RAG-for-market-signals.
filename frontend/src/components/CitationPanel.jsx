import { motion, AnimatePresence } from "framer-motion"
import { TextureCard, TextureCardContent } from "./ui/texture-card"
import { Bookmark, Mic, FileText, Globe, BarChart2 } from "lucide-react"

const MODALITY_ICONS = {
  audio: Mic,
  document: FileText,
  news: Globe,
  image: BarChart2,
}

export default function CitationPanel({ citations, activeCitation, onCitationSelect }) {
  if (!citations.length) return null

  return (
    <TextureCard className="w-full sticky top-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <Bookmark className="text-pink-400 w-5 h-5" />
          <span className="text-xs font-bold text-neutral-400 uppercase tracking-widest font-title">
            Source Citations ({citations.length})
          </span>
        </div>
      </div>

      <TextureCardContent className="p-4 flex flex-col gap-3.5 max-h-[75vh] overflow-y-auto">
        {citations.map((citation, i) => {
          const isActive = activeCitation === i
          const ModalityIcon = MODALITY_ICONS[citation.modality] || FileText
          return (
            <div
              key={citation.id || i}
              onClick={() => onCitationSelect(isActive ? null : i)}
              className={`group flex flex-col border rounded-xl p-3 cursor-pointer transition-all duration-300 ${
                isActive
                  ? "bg-neutral-900/80 border-pink-500/30 shadow-[0_0_12px_rgba(212,68,239,0.1)]"
                  : "bg-neutral-950/40 border-white/5 hover:border-white/10 hover:bg-neutral-900/30"
              }`}
            >
              {/* Citation Item Header */}
              <div className="flex items-center justify-between w-full mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold font-mono text-neutral-500">
                    [{i + 1}]
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider flex items-center gap-1 ${
                      citation.modality === "audio"
                        ? "bg-sky-500/10 border border-sky-500/30 text-sky-400"
                        : citation.modality === "document"
                        ? "bg-violet-500/10 border border-violet-500/30 text-violet-400"
                        : citation.modality === "news"
                        ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400"
                        : "bg-pink-500/10 border border-pink-500/30 text-pink-400"
                    }`}
                  >
                    <ModalityIcon className="w-3 h-3" />
                    {" "}{citation.modality}
                  </span>
                </div>
                {citation.confidence > 0 && (
                  <span className="text-[10px] font-mono text-neutral-500 font-bold pl-2">
                    {(citation.confidence * 100).toFixed(0)}% Match
                  </span>
                )}
              </div>

              {/* Excerpt Animation with AnimatePresence */}
              <AnimatePresence initial={false}>
                {isActive ? (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: "easeOut" }}
                    className="overflow-hidden mt-2 border-t border-white/5 pt-2"
                  >
                    <p className="text-xs text-neutral-300 italic leading-relaxed mb-2 font-medium">
                      "{citation.chunk_excerpt}"
                    </p>
                    <div className="flex items-center justify-between text-[10px] text-neutral-500">
                      <span>{citation.ticker} {citation.filed_date && ` · ${citation.filed_date}`}</span>
                      {citation.source_url && (
                        <a
                          href={citation.source_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()} // Stop accordion toggling when clicking the link
                          className="text-pink-400 hover:text-pink-300 font-bold transition-colors"
                        >
                          Source ↗
                        </a>
                      )}
                    </div>
                  </motion.div>
                ) : (
                  <p className="text-xs text-neutral-400 truncate mt-1 w-full pl-6 select-none">
                    {citation.chunk_excerpt}
                  </p>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </TextureCardContent>
    </TextureCard>
  )
}
