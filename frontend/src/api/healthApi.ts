import type { SpecSummary } from '../types'

export async function fetchHealth(baseUrl: string): Promise<boolean> {
  const base = baseUrl.replace(/\/+$/, '')
  try {
    const response = await fetch(`${base}/v1/health`)
    return response.ok
  } catch {
    return false
  }
}

export async function fetchSpecSummary(
  baseUrl: string,
  sessionId: string,
): Promise<SpecSummary | null> {
  const base = baseUrl.replace(/\/+$/, '')
  try {
    const response = await fetch(
      `${base}/v1/sessions/${encodeURIComponent(sessionId)}/spec`,
    )
    if (!response.ok) return null
    const data = (await response.json()) as unknown
    if (isSpecSummary(data)) return data
    return null
  } catch {
    return null
  }
}

function isSpecSummary(value: unknown): value is SpecSummary {
  if (typeof value !== 'object' || value === null) return false
  const obj = value as Record<string, unknown>
  return (
    typeof obj.spec_version_id === 'string' &&
    Array.isArray(obj.steps)
  )
}
