import { useMemo, useState } from 'react'
import { AddItemForm } from './components/AddItemForm.jsx'
import { AnswerView } from './components/AnswerView.jsx'
import { AskPanel } from './components/AskPanel.jsx'
import { ErrorBanner } from './components/ErrorBanner.jsx'
import { ItemList } from './components/ItemList.jsx'
import { useAsk } from './hooks/useAsk.js'
import { useHealth } from './hooks/useHealth.js'
import { useItems } from './hooks/useItems.js'

export default function App() {
  const { items, loading, error: itemsError, pendingCount, add, remove } = useItems()
  const { result, asking, error: askError, ask } = useAsk()
  const [deleteError, setDeleteError] = useState(null)

  // Items backing the current answer get highlighted in the list, so the
  // connection between an answer and the things you saved stays visible.
  const citedItemIds = useMemo(
    () => new Set((result?.citations ?? []).map((citation) => citation.item_id)),
    [result],
  )

  const readyCount = items.filter((item) => item.status === 'ready').length
  // Re-read /health as items finish indexing, so the counter is not frozen
  // at whatever was true when the page loaded.
  const health = useHealth(readyCount)

  async function handleDelete(id) {
    setDeleteError(null)
    try {
      await remove(id)
    } catch (cause) {
      setDeleteError(cause)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-baseline justify-between px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">AI Knowledge Inbox</h1>
            <p className="text-sm text-slate-500">Save notes and links, then ask questions answered from them.</p>
          </div>
          {health && (
            <p className="hidden text-xs text-slate-400 sm:block" title="Active providers">
              {health.providers.llm}/{health.providers.llm_model} · {health.chunks} chunks indexed
            </p>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-6">
        {health?.providers.llm === 'local' && (
          <p className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
            Running without an API key: answers are quoted directly from your saved text rather than written by a
            model. Set <code className="font-mono text-xs">OPENAI_API_KEY</code> or{' '}
            <code className="font-mono text-xs">ANTHROPIC_API_KEY</code> and restart for generated answers.
          </p>
        )}

        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-8">
            <AddItemForm onAdd={add} />
            <ErrorBanner error={deleteError} onDismiss={() => setDeleteError(null)} />
            <ItemList
              items={items}
              loading={loading}
              error={itemsError}
              pendingCount={pendingCount}
              citedItemIds={citedItemIds}
              onDelete={handleDelete}
            />
          </div>

          <div className="space-y-4">
            <AskPanel onAsk={ask} asking={asking} error={askError} disabled={readyCount === 0} />
            <AnswerView result={result} />
          </div>
        </div>
      </main>
    </div>
  )
}
