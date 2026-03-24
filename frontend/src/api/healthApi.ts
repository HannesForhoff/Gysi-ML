import type { SpecStepSummary, SpecSummary } from '../types'

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
