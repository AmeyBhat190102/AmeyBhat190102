/** Presentation helpers shared by more than one component. */

export function formatTimestamp(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  const secondsAgo = Math.floor((Date.now() - date.getTime()) / 1000)
  if (secondsAgo < 60) return 'just now'
  if (secondsAgo < 3600) return `${Math.floor(secondsAgo / 60)}m ago`
  if (secondsAgo < 86_400) return `${Math.floor(secondsAgo / 3600)}h ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function hostOf(url) {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

/** A note or a URL? Decided here so the form and the API agree. */
export function looksLikeUrl(text) {
  const trimmed = text.trim()
  return /^https?:\/\/\S+$/i.test(trimmed)
}
