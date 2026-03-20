import type { ArtifactRef, RunStatus, RunStatusResponse } from '../types'

export async function fetchRunStatus(
  baseUrl: string,
  sessionId: string,
  runId: string,
): Promise<RunStatusResponse> {
  const base = baseUrl.replace(/\/+$/, '')
  const url = `${base}/v1/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(runId)}`

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Run-Status-Abfrage fehlgeschlagen (HTTP ${response.status})`)
  }

  const data: unknown = await response.json()
  return parseRunStatusResponse(data)
}

function parseRunStatusResponse(data: unknown): RunStatusResponse {
  if (!isRecord(data)) {
    throw new Error('Run-Status-Response ist kein Objekt.')
  }

  const status = parseRunStatus(data.status)

  const metrics = isRecord(data.metrics)
    ? toMetrics(data.metrics)
    : undefined

  const artifacts = Array.isArray(data.artifacts)
    ? parseArtifacts(data.artifacts)
    : undefined

  const error_message =
    typeof data.error_message === 'string' && data.error_message.length > 0
      ? data.error_message
      : undefined

  return { status, metrics, artifacts, error_message }
}

const VALID_STATUSES = new Set<RunStatus>(['queued', 'running', 'done', 'failed'])

function parseRunStatus(value: unknown): RunStatus {
  if (typeof value === 'string' && VALID_STATUSES.has(value as RunStatus)) {
    return value as RunStatus
  }
  throw new Error(`Ungültiger Run-Status: ${String(value)}`)
}

function parseArtifacts(raw: unknown[]): ArtifactRef[] {
  const result: ArtifactRef[] = []
  for (const item of raw) {
    if (!isRecord(item)) continue
    // Backend: artifact_id + type; Frontend: id + media_type
    const id = toNonEmptyString(item.artifact_id) ?? toNonEmptyString(item.id) ?? ''
    const label = toNonEmptyString(item.label) ?? toNonEmptyString(item.type) ?? 'Artifact'
    const url = toNonEmptyString(item.href) ?? toNonEmptyString(item.url) ?? ''
    const media_type = toNonEmptyString(item.media_type) ?? toNonEmptyString(item.type) ?? ''
    if (id && url) {
      result.push({ id, label, url, media_type })
    }
  }
  return result
}

function toMetrics(obj: Record<string, unknown>): Record<string, number | string> {
  const result: Record<string, number | string> = {}
  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === 'number' || typeof value === 'string') {
      result[key] = value
    }
  }
  return result
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function toNonEmptyString(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}
