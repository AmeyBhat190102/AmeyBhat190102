import { firstFieldMessage } from '../lib/api.js'

/** Shows a backend error, including the request id for log correlation. */
export function ErrorBanner({ error, onDismiss }) {
  if (!error) return null

  const fieldMessage = firstFieldMessage(error)
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
      <div className="flex-1">
        <p className="font-medium">{error.message}</p>
        {fieldMessage && <p className="mt-1 text-rose-700">{fieldMessage}</p>}
        {error.requestId && (
          <p className="mt-1 font-mono text-xs text-rose-600">request id: {error.requestId}</p>
        )}
      </div>
      {onDismiss && (
        <button type="button" onClick={onDismiss} className="text-rose-500 hover:text-rose-700" aria-label="Dismiss error">
          ✕
        </button>
      )}
    </div>
  )
}
