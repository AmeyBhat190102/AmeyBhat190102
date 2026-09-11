import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api.js'

const POLL_INTERVAL_MS = 1200
const ACTIVE_STATUSES = new Set(['pending', 'processing'])

/**
 * Owns the saved-items list.
 *
 * Ingestion is asynchronous on the server, so a new item arrives as `pending`
 * and becomes `ready` later. This hook polls while anything is still in
 * flight and stops as soon as everything has settled, so an idle inbox makes
 * no requests at all.
 */
export function useItems() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const refresh = useCallback(async (signal) => {
    try {
      const page = await api.listItems({ signal })
      if (!mounted.current) return
      setItems(page.items)
      setError(null)
    } catch (cause) {
      if (cause.name === 'AbortError' || !mounted.current) return
      setError(cause)
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    refresh(controller.signal)
    return () => controller.abort()
  }, [refresh])

  const pendingCount = useMemo(() => items.filter((item) => ACTIVE_STATUSES.has(item.status)).length, [items])

  useEffect(() => {
    if (pendingCount === 0) return undefined
    const controller = new AbortController()
    const timer = setInterval(() => refresh(controller.signal), POLL_INTERVAL_MS)
    return () => {
      clearInterval(timer)
      controller.abort()
    }
  }, [pendingCount, refresh])

  const add = useCallback(async ({ url, content, title }) => {
    // Show the item the instant the server accepts it; polling fills in the
    // rest once the worker has processed it.
    const created = url ? await api.ingestUrl(url, title) : await api.ingestNote(content, title)
    if (mounted.current) setItems((current) => [created, ...current])
    return created
  }, [])

  const remove = useCallback(async (id) => {
    setItems((current) => current.filter((item) => item.id !== id))
    try {
      await api.deleteItem(id)
    } catch (cause) {
      // The delete did not happen. Re-read rather than restoring a snapshot,
      // which a poll in flight may already have superseded.
      await refresh()
      throw cause
    }
  }, [refresh])

  return { items, loading, error, pendingCount, refresh, add, remove }
}
