import type { SpecStepSummary, SpecSummary, VersionNode, VersionTree } from '../types'

export interface HealthResult {
  healthy: boolean
  llmModel: string | null
}

export async function fetchHealth(baseUrl: string): Promise<HealthResult> {
  const base = baseUrl.replace(/\/+$/, '')
  try {
    const response = await fetch(`${base}/v1/health`)
    if (!response.ok) return { healthy: false, llmModel: null }
    const data = (await response.json()) as Record<string, unknown>
    const llmModel = typeof data.llm_model === 'string' && data.llm_model ? data.llm_model : null
    return { healthy: true, llmModel }
  } catch {
    return { healthy: false, llmModel: null }
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
    return parseSpecSummary(data)
  } catch {
    return null
  }
}

/**
 * Mappt die Backend-SpecVersionResponse auf das Frontend-SpecSummary-Format.
 *
 * Backend: { version: string, spec: { steps: [{type, enabled?, params?}] }, ... }
 * Frontend: { spec_version_id: string, steps: [{step_type, enabled}] }
 */
function parseSpecSummary(value: unknown): SpecSummary | null {
  if (typeof value !== 'object' || value === null) return null
  const obj = value as Record<string, unknown>

  // Backend-Format: version + spec.steps
  if (typeof obj.version === 'string' && isRecord(obj.spec)) {
    const spec = obj.spec
    if (!Array.isArray(spec.steps)) return null
    const steps = parseSteps(spec.steps)
    if (steps === null) return null
    return { spec_version_id: obj.version, steps }
  }

  // Direktes Frontend-Format (z.B. aus Message-Response)
  if (typeof obj.spec_version_id === 'string' && Array.isArray(obj.steps)) {
    const steps = parseSteps(obj.steps)
    if (steps === null) return null
    return {
      spec_version_id: obj.spec_version_id,
      steps,
      notes: typeof obj.notes === 'string' ? obj.notes : undefined,
    }
  }

  return null
}

function parseSteps(raw: unknown[]): SpecStepSummary[] | null {
  const steps: SpecStepSummary[] = []
  for (const item of raw) {
    if (!isRecord(item)) return null
    // Backend-steps haben "type"; Frontend-SpecStepSummary hat "step_type"
    const stepType =
      typeof item.step_type === 'string'
        ? item.step_type
        : typeof item.type === 'string'
          ? item.type
          : null
    if (stepType === null) return null
    steps.push({ step_type: stepType, enabled: item.enabled !== false })
  }
  return steps
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export async function fetchSpecTree(
  baseUrl: string,
  sessionId: string,
): Promise<VersionTree | null> {
  const base = baseUrl.replace(/\/+$/, '')
  try {
    const response = await fetch(
      `${base}/v1/sessions/${encodeURIComponent(sessionId)}/spec/tree`,
    )
    if (!response.ok) return null
    const data = (await response.json()) as unknown
    return parseVersionTree(data)
  } catch {
    return null
  }
}

function parseVersionNode(item: unknown): VersionNode | null {
  if (!isRecord(item)) return null
  if (typeof item.spec_id !== 'string' || typeof item.version !== 'string') return null
  return {
    spec_id: item.spec_id,
    version: item.version,
    parent_spec_id: typeof item.parent_spec_id === 'string' ? item.parent_spec_id : null,
    change_summary: typeof item.change_summary === 'string' ? item.change_summary : null,
    created_at: typeof item.created_at === 'string' ? item.created_at : '',
    has_runs: item.has_runs === true,
    last_run_status: typeof item.last_run_status === 'string' ? item.last_run_status : null,
    last_run_id: typeof item.last_run_id === 'string' ? item.last_run_id : null,
    phase: typeof item.phase === 'string' ? item.phase : 'preprocessing',
  }
}

function parseVersionTree(value: unknown): VersionTree | null {
  if (!isRecord(value)) return null
  if (typeof value.session_id !== 'string') return null
  if (!Array.isArray(value.versions)) return null

  const versions: VersionNode[] = []
  for (const item of value.versions) {
    const node = parseVersionNode(item)
    if (node === null) return null
    versions.push(node)
  }

  return {
    session_id: value.session_id,
    active_spec_id: typeof value.active_spec_id === 'string' ? value.active_spec_id : null,
    versions,
  }
}

export async function performRollback(
  baseUrl: string,
  sessionId: string,
  targetSpecId: string,
): Promise<{ ok: true; newVersion: string } | { ok: false; error: string }> {
  const base = baseUrl.replace(/\/+$/, '')
  try {
    const response = await fetch(
      `${base}/v1/sessions/${encodeURIComponent(sessionId)}/rollback`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_spec_id: targetSpecId }),
      },
    )
    if (!response.ok) {
      const err = (await response.json()) as Record<string, unknown>
      return { ok: false, error: String(err.detail ?? 'Rollback fehlgeschlagen') }
    }
    const data = (await response.json()) as Record<string, unknown>
    return { ok: true, newVersion: String(data.new_version ?? '?') }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Netzwerkfehler' }
  }
}
