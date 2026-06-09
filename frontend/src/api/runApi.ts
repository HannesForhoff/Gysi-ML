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
  return parseRunStatusResponse(data, base)
}

function parseRunStatusResponse(data: unknown, baseUrl: string): RunStatusResponse {
  if (!isRecord(data)) {
    throw new Error('Run-Status-Response ist kein Objekt.')
  }

  const status = parseRunStatus(data.status)

  const metrics = isRecord(data.metrics)
    ? toMetrics(data.metrics)
    : undefined

  const artifacts = Array.isArray(data.artifacts)
    ? parseArtifacts(
        data.artifacts,
        baseUrl,
        toNonEmptyString(data.run_id),
        toNonEmptyString(data.spec_version),
      )
    : undefined

  const error_message =
    typeof data.error_message === 'string' && data.error_message.length > 0
      ? data.error_message
      : undefined

  const step_results = Array.isArray(data.step_results)
    ? data.step_results
        .filter(isRecord)
        .map((sr) => ({
          step_type: toNonEmptyString(sr.step_type) ?? 'unknown',
          metadata: isRecord(sr.metadata) ? (sr.metadata as Record<string, unknown>) : {},
        }))
    : undefined

  const suggested_next_steps = Array.isArray(data.suggested_next_steps)
    ? (data.suggested_next_steps as unknown[]).filter((s): s is string => typeof s === 'string')
    : undefined

  return { status, metrics, artifacts, error_message, step_results, suggested_next_steps }
}

const VALID_STATUSES = new Set<RunStatus>(['queued', 'running', 'done', 'failed'])

const STATUS_ALIASES: Record<string, RunStatus> = {
  completed: 'done',
}

function parseRunStatus(value: unknown): RunStatus {
  if (typeof value !== 'string') {
    throw new Error(`Ungültiger Run-Status: ${String(value)}`)
  }
  const mapped = STATUS_ALIASES[value]
  if (mapped) return mapped
  if (VALID_STATUSES.has(value as RunStatus)) {
    return value as RunStatus
  }
  throw new Error(`Ungültiger Run-Status: ${String(value)}`)
}

function parseArtifacts(raw: unknown[], baseUrl: string, runId?: string | null, specVersion?: string | null): ArtifactRef[] {
  const base = baseUrl.replace(/\/+$/, '')
  const result: ArtifactRef[] = []
  for (const item of raw) {
    if (!isRecord(item)) continue
    // Backend: artifact_id + type; Frontend: id + media_type
    const id = toNonEmptyString(item.artifact_id) ?? toNonEmptyString(item.id) ?? ''
    const artifactType = toNonEmptyString(item.type) ?? ''
    const label = toNonEmptyString(item.label) ?? artifactTypeToLabel(artifactType)
    const url = toNonEmptyString(item.href)
      ?? toNonEmptyString(item.url)
      ?? (id && base ? `${base}/v1/artifacts/${encodeURIComponent(id)}` : '')
    const media_type = toNonEmptyString(item.media_type) ?? artifactTypeToMime(artifactType)
    const eff_run_id = toNonEmptyString(item.run_id) ?? runId
    const eff_spec_version = toNonEmptyString(item.spec_version) ?? specVersion
    if (id && url) {
      result.push({
        id, label, url, media_type,
        ...(eff_run_id ? { run_id: eff_run_id } : {}),
        ...(eff_spec_version ? { spec_version: eff_spec_version } : {}),
      })
    }
  }
  return result
}

function artifactTypeToLabel(type: string): string {
  const labels: Record<string, string> = {
    split_train: 'Trainingsdaten (CSV)',
    split_test: 'Testdaten (CSV)',
    feature_importance: 'Feature Importance',
    ebm_global_explanation: 'EBM Global Explanation',
    correlation_filter: 'Korrelations-Filter (CSV)',
    plot_distribution: 'Verteilungsplot',
    lr_coefficients: 'Lineare Regression – Koeffizienten',
  }
  return labels[type] ?? (type || 'Artifact')
}

function artifactTypeToMime(type: string): string {
  if (type === 'split_train' || type === 'split_test') return 'text/csv'
  if (type === 'correlation_filter') return 'text/csv'
  if (type === 'feature_importance' || type === 'ebm_global_explanation' || type === 'plot_distribution' || type === 'lr_coefficients') return 'image/png'
  return 'application/octet-stream'
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
