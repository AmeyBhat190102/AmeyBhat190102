const STYLES = {
  pending: 'bg-amber-50 text-amber-700 border-amber-200',
  processing: 'bg-amber-50 text-amber-700 border-amber-200',
  ready: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  failed: 'bg-rose-50 text-rose-700 border-rose-200',
}

const LABELS = {
  pending: 'Queued',
  processing: 'Indexing',
  ready: 'Indexed',
  failed: 'Failed',
}

export function StatusBadge({ status }) {
  const busy = status === 'pending' || status === 'processing'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${STYLES[status] ?? STYLES.pending}`}
    >
      {busy && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />}
      {LABELS[status] ?? status}
    </span>
  )
}
