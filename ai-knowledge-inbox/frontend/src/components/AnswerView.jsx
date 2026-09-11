import { useState } from 'react'
import { hostOf } from '../lib/format.js'

const MARKER = /(\[\d+\])/g

/**
 * Renders the answer with its [n] markers turned into controls that reveal
 * the passage they came from. Showing the evidence next to the claim is the
 * point of a RAG UI: without it the user has no way to tell a grounded answer
 * from a fluent guess.
 */
function AnswerText({ text, citationCount, activeMarker, onSelectMarker }) {
  return (
    <p className="text-[15px] leading-relaxed text-slate-800">
      {text.split(MARKER).map((segment, index) => {
        const match = /^\[(\d+)\]$/.exec(segment)
        if (!match) return <span key={index}>{segment}</span>

        const marker = Number(match[1])
        if (marker < 1 || marker > citationCount) {
          // The model referenced a passage that was not in its context.
          return (
            <sup key={index} className="ml-0.5 text-xs text-slate-400" title="Unknown source">
              [{marker}]
            </sup>
          )
        }
        return (
          <button
            key={index}
            type="button"
            onClick={() => onSelectMarker(marker === activeMarker ? null : marker)}
            className={`mx-0.5 rounded px-1 align-super text-xs font-medium transition ${
              marker === activeMarker ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
            }`}
            aria-label={`Show source ${marker}`}
          >
            {marker}
          </button>
        )
      })}
    </p>
  )
}

function CitationCard({ citation, active, onSelect }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(active ? null : citation.marker)}
        className={`w-full rounded-lg border p-3 text-left transition ${
          active ? 'border-blue-400 bg-blue-50/50' : 'border-slate-200 bg-white hover:border-slate-300'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-blue-600 text-xs font-medium text-white">
            {citation.marker}
          </span>
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900">{citation.title}</span>
          <span className="shrink-0 text-xs tabular-nums text-slate-400" title="Hybrid relevance score">
            {citation.score.toFixed(2)}
          </span>
        </div>

        <p className="mt-2 text-sm leading-relaxed text-slate-600">{citation.snippet}</p>

        {citation.source_url && (
          <a
            href={citation.source_url}
            target="_blank"
            rel="noreferrer noopener"
            onClick={(event) => event.stopPropagation()}
            className="mt-2 inline-block text-xs text-blue-600 hover:underline"
          >
            {hostOf(citation.source_url)} ↗
          </a>
        )}
      </button>
    </li>
  )
}

export function AnswerView({ result }) {
  const [activeMarker, setActiveMarker] = useState(null)
  if (!result) return null

  const { answer, citations, grounded, provider, model, latency_ms: latencyMs, chunks_searched: chunksSearched } = result

  return (
    <section aria-live="polite" className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Answer</h2>
        {grounded ? (
          <AnswerText
            text={answer}
            citationCount={citations.length}
            activeMarker={activeMarker}
            onSelectMarker={setActiveMarker}
          />
        ) : (
          <p className="rounded-md bg-slate-50 px-3 py-2 text-[15px] text-slate-600">{answer}</p>
        )}
      </div>

      {citations.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Sources ({citations.length})
          </h3>
          <ul className="space-y-2">
            {citations.map((citation) => (
              <CitationCard
                key={citation.chunk_id}
                citation={citation}
                active={citation.marker === activeMarker}
                onSelect={setActiveMarker}
              />
            ))}
          </ul>
        </div>
      )}

      <p className="border-t border-slate-100 pt-3 text-xs text-slate-400">
        {provider}/{model} · searched {chunksSearched} chunk{chunksSearched === 1 ? '' : 's'} · {latencyMs} ms
      </p>
    </section>
  )
}
