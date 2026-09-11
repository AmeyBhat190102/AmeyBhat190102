import { useState } from 'react'
import { looksLikeUrl } from '../lib/format.js'
import { ErrorBanner } from './ErrorBanner.jsx'

/**
 * One box for both kinds of input.
 *
 * The API keeps note and url as separate, explicit request shapes; the form
 * decides which one to send by looking at what was typed, so the user never
 * has to pick a type from a menu. The badge shows the decision before saving,
 * and the override lets them correct it.
 */
export function AddItemForm({ onAdd }) {
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [forcedType, setForcedType] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const detected = looksLikeUrl(text) ? 'url' : 'note'
  const type = forcedType ?? detected
  const canSubmit = text.trim().length > 0 && !submitting

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canSubmit) return

    setSubmitting(true)
    setError(null)
    try {
      await onAdd(
        type === 'url'
          ? { url: text.trim(), title: title.trim() || undefined }
          : { content: text, title: title.trim() || undefined },
      )
      setText('')
      setTitle('')
      setForcedType(null)
    } catch (cause) {
      setError(cause)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label htmlFor="content" className="mb-1.5 block text-sm font-medium text-slate-700">
          Save a note or a link
        </label>
        <textarea
          id="content"
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setForcedType(null)
          }}
          rows={4}
          placeholder={'Paste a URL, or type a note…\n\nCtrl+Enter to save'}
          className="w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none"
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') handleSubmit(event)
          }}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Saving as</span>
          {['note', 'url'].map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setForcedType(option)}
              aria-pressed={type === option}
              className={`rounded-md border px-2 py-1 font-medium transition ${
                type === option
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
              }`}
            >
              {option === 'url' ? 'Link' : 'Note'}
            </button>
          ))}
        </div>

        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Title (optional)"
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none"
        />

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {submitting ? 'Saving…' : 'Save'}
        </button>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
    </form>
  )
}
