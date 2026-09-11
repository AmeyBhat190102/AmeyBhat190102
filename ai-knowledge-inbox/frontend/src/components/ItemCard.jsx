import { useState } from 'react'
import { formatTimestamp, hostOf } from '../lib/format.js'
import { StatusBadge } from './StatusBadge.jsx'

export function ItemCard({ item, onDelete, highlighted }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <li
      className={`rounded-lg border bg-white p-4 transition ${
        highlighted ? 'border-blue-400 ring-2 ring-blue-100' : 'border-slate-200'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-medium text-slate-900">{item.title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            <StatusBadge status={item.status} />
            {item.source_url ? (
              <a
                href={item.source_url}
                target="_blank"
                rel="noreferrer noopener"
                className="truncate text-blue-600 hover:underline"
              >
                {hostOf(item.source_url)}
              </a>
            ) : (
              <span>note</span>
            )}
            <span>{formatTimestamp(item.created_at)}</span>
            {item.status === 'ready' && (
              <span>
                {item.chunk_count} chunk{item.chunk_count === 1 ? '' : 's'} · {item.char_count.toLocaleString()} chars
              </span>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={() => onDelete(item.id)}
          className="shrink-0 rounded-md px-2 py-1 text-xs text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
          aria-label={`Delete ${item.title}`}
        >
          Delete
        </button>
      </div>

      {item.error_message && (
        <p className="mt-2 rounded-md bg-rose-50 px-2 py-1.5 text-xs text-rose-700">{item.error_message}</p>
      )}

      {item.preview && (
        <div className="mt-2">
          <p className={`text-sm text-slate-600 ${expanded ? '' : 'line-clamp-2'}`}>{item.preview}</p>
          {item.preview.length > 140 && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="mt-1 text-xs font-medium text-blue-600 hover:underline"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
      )}
    </li>
  )
}
