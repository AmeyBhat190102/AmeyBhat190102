import { useState } from 'react'
import { ErrorBanner } from './ErrorBanner.jsx'

const SUGGESTIONS = ['What did I save about this?', 'Summarise the main tradeoff']

export function AskPanel({ onAsk, asking, error, disabled }) {
  const [question, setQuestion] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    const trimmed = question.trim()
    if (trimmed.length >= 3 && !asking) onAsk(trimmed)
  }

  return (
    <section aria-labelledby="ask-heading" className="space-y-3">
      <h2 id="ask-heading" className="text-sm font-semibold text-slate-900">
        Ask your inbox
      </h2>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={disabled ? 'Save something first…' : 'Ask a question about your saved content'}
          disabled={disabled}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={asking || disabled || question.trim().length < 3}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {asking ? 'Thinking…' : 'Ask'}
        </button>
      </form>

      {!disabled && !question && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => setQuestion(suggestion)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 transition hover:border-slate-300"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <ErrorBanner error={error} />
    </section>
  )
}
