/**
 * The single place that knows how to talk to the backend.
 *
 * Every call funnels through `request`, so error handling, JSON parsing and
 * the request-id passthrough are written once. Errors arrive as ApiError with
 * the backend's own code and message, which is what the UI shows the user.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, { code = 'request_failed', status = 0, details = null, requestId = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
    this.requestId = requestId
  }
}

/** Turn the backend's `{error: {...}}` body into an ApiError. */
async function toApiError(response) {
  const requestId = response.headers.get('X-Request-ID')
  let body = null
  try {
    body = await response.json()
  } catch {
    // A proxy or a crash can return non-JSON; fall through to a generic message.
  }

  const error = body?.error
  if (error?.message) {
    return new ApiError(error.message, {
      code: error.code,
      status: response.status,
      details: error.details ?? null,
      requestId,
    })
  }
  return new ApiError(`Request failed with status ${response.status}`, {
    status: response.status,
    requestId,
  })
}

async function request(path, { method = 'GET', body, signal } = {}) {
  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause
    throw new ApiError('Cannot reach the API. Is the backend running?', { code: 'network_error' })
  }

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return null
  return response.json()
}

/** First 422 field message, if the backend rejected the body. */
export function firstFieldMessage(error) {
  const field = error?.details?.fields?.[0]
  return field ? `${field.field}: ${field.message}` : null
}

export const api = {
  ingestNote: (content, title) => request('/ingest', { method: 'POST', body: { type: 'note', content, ...(title ? { title } : {}) } }),
  ingestUrl: (url, title) => request('/ingest', { method: 'POST', body: { type: 'url', url, ...(title ? { title } : {}) } }),
  listItems: ({ limit = 50, signal } = {}) => request(`/items?limit=${limit}`, { signal }),
  getItem: (id) => request(`/items/${id}`),
  deleteItem: (id) => request(`/items/${id}`, { method: 'DELETE' }),
  ask: (question, { topK, itemIds, signal } = {}) =>
    request('/query', {
      method: 'POST',
      signal,
      body: { question, ...(topK ? { top_k: topK } : {}), ...(itemIds?.length ? { item_ids: itemIds } : {}) },
    }),
  health: ({ signal } = {}) => request('/health', { signal }),
}
