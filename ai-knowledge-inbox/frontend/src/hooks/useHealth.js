import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'

/**
 * Reads /health, re-reading whenever `refreshKey` changes.
 *
 * Worth surfacing in the UI: it tells the user whether answers are coming
 * from a real model or from the offline fallback, which otherwise looks like
 * a badly behaved LLM. The key exists so the indexed-chunk count follows
 * ingestion instead of showing whatever was true at page load.
 */
export function useHealth(refreshKey = 0) {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    api
      .health({ signal: controller.signal })
      .then(setHealth)
      .catch(() => setHealth(null))
    return () => controller.abort()
  }, [refreshKey])

  return health
}
