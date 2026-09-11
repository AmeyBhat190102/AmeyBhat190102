import { ErrorBanner } from './ErrorBanner.jsx'
import { ItemCard } from './ItemCard.jsx'

export function ItemList({ items, loading, error, pendingCount, citedItemIds, onDelete }) {
  if (loading) {
    return <p className="py-8 text-center text-sm text-slate-500">Loading saved items…</p>
  }

  return (
    <section aria-labelledby="saved-heading" className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 id="saved-heading" className="text-sm font-semibold text-slate-900">
          Saved items <span className="font-normal text-slate-500">({items.length})</span>
        </h2>
        {pendingCount > 0 && (
          <span className="text-xs text-amber-600">
            {pendingCount} indexing…
          </span>
        )}
      </div>

      <ErrorBanner error={error} />

      {items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
          Nothing saved yet. Add a note or paste a link to get started.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              onDelete={onDelete}
              highlighted={citedItemIds.has(item.id)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
