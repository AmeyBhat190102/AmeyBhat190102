import { useCallback, useRef, useState } from 'react'
import { api } from '../lib/api.js'

/**
 * Owns one question at a time.
 *
 * Asking again while a request is in flight cancels the first: the user has
 * moved on, and a late response overwriting a newer one is a classic race.
 */
export function useAsk() {
  const [result, setResult] = useState(null)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState(null)
  const inFlight = useRef(null)

  const ask = useCallback(async (question, options = {}) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller

    setAsking(true)
    setError(null)
    try {
      const answer = await api.ask(question, { ...options, signal: controller.signal })
      if (!controller.signal.aborted) setResult(answer)
      return answer
    } catch (cause) {
      if (cause.name !== 'AbortError') setError(cause)
      return null
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null
        setAsking(false)
      }
    }
  }, [])

  const reset = useCallback(() => {
    inFlight.current?.abort()
    setResult(null)
    setError(null)
  }, [])

  return { result, asking, error, ask, reset }
}
