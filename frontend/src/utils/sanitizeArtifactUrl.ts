export function sanitizeArtifactUrl(rawUrl: string): string | null {
  const trimmed = rawUrl.trim()

  if (trimmed.length === 0) {
    return null
  }

  if (trimmed.startsWith('//')) {
    return null
  }

  if (trimmed.startsWith('/')) {
    return trimmed
  }

  try {
    const parsed = new URL(trimmed, 'http://localhost')
    const isHttp = parsed.protocol === 'http:' || parsed.protocol === 'https:'

    if (!isHttp) {
      return null
    }

    const isAbsolute = /^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(trimmed)
    return isAbsolute ? parsed.toString() : trimmed
  } catch {
    return null
  }
}
