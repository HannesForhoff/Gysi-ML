import type { ArtifactRef, AssistantResponse, SpecSummary, StepResult } from '../types'
import type {
  ConfirmResult,
  SendAssistantMessageInput,
  SendAssistantMessageResult,
} from './transportTypes'

export async function sendRealMessage(
  backendBaseUrl: string,
  input: SendAssistantMessageInput,
): Promise<SendAssistantMessageResult> {
  const baseUrl = backendBaseUrl.replace(/\/+$/, '')
  let sessionId = toNonEmptyString(input.sessionId)

  if (!sessionId) {
    const sessionResponse = await fetch(`${baseUrl}/v1/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })

    const sessionBody = await parseJsonBody(sessionResponse)

    if (!sessionResponse.ok) {
      return {
        sessionId: null,
        response: toAssistantResponse(
          sessionBody,
          `Session creation failed with HTTP ${sessionResponse.status}`,
          baseUrl,
        ),
      }
    }

    sessionId = extractSessionId(sessionBody)

    if (!sessionId) {
      return {
        sessionId: null,
        response: {
          type: 'error',
          message: 'Session creation response did not include session_id.',
        },
      }
    }
  }

  const messageResponse = await fetch(
    `${baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: input.userText }),
    },
  )

  const messageBody = await parseJsonBody(messageResponse)

  if (!messageResponse.ok) {
    return {
      sessionId,
      response: toAssistantResponse(
        messageBody,
        `Message request failed with HTTP ${messageResponse.status}`,
        baseUrl,
      ),
    }
  }

  return {
    sessionId,
    response: toAssistantResponse(
      messageBody,
      'Backend response could not be interpreted.',
      baseUrl,
    ),
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function toNonEmptyString(value: unknown): string | null {
  if (typeof value !== 'string') return null

  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function extractSessionId(payload: unknown): string | null {
  if (!isRecord(payload)) return null
  return toNonEmptyString(payload.session_id)
}

async function parseJsonBody(response: Response): Promise<unknown> {
  const bodyText = await response.text()

  if (!bodyText.trim()) {
    return null
  }

  try {
    return JSON.parse(bodyText) as unknown
  } catch {
    return null
  }
}

function toAssistantResponse(
  payload: unknown,
  fallbackMessage: string,
  baseUrl: string,
): AssistantResponse {
  if (!isRecord(payload)) {
    return { type: 'error', message: fallbackMessage }
  }

  const type = payload.type

  // Backend proposal: { type:'proposal', steps:[{type, params}], explanation }
  if (type === 'proposal') {
    const message =
      toNonEmptyString(payload.explanation) ??
      toNonEmptyString(payload.message) ??
      fallbackMessage
    const rawSteps = Array.isArray(payload.steps) ? payload.steps : []
    const steps = rawSteps.map((s) => {
      const step = isRecord(s) ? s : {}
      // Backend uses 'type', frontend uses 'step_type'
      const stepType = toNonEmptyString(step.step_type ?? step.type) ?? ''
      const params = isRecord(step.params) ? step.params : undefined
      // LLM-geschriebene parameters_summary bevorzugen (lesbares Deutsch),
      // als Fallback die technische k=v-Darstellung der params verwenden.
      const llmSummary = toNonEmptyString(step.parameters_summary) ?? undefined
      const paramsSummary = llmSummary
        ?? (params
          ? Object.entries(params)
              .map(([k, v]) => `${k}=${String(v)}`)
              .join(', ')
          : undefined)
      return {
        step_type: stepType,
        ...(typeof step.enabled === 'boolean' ? { enabled: step.enabled } : {}),
        ...(paramsSummary ? { parameters_summary: paramsSummary } : {}),
      }
    })
    const proposalId = toNonEmptyString(payload.proposal_id) ?? undefined
    const dataLeakageWarning = payload.data_leakage_warning === true
    const leakageSteps = Array.isArray(payload.leakage_steps)
      ? (payload.leakage_steps as string[])
      : undefined
    return {
      type: 'proposal',
      message,
      steps,
      ...(proposalId ? { proposal_id: proposalId } : {}),
      ...(dataLeakageWarning ? { data_leakage_warning: true } : {}),
      ...(leakageSteps?.length ? { leakage_steps: leakageSteps } : {}),
    }
  }

  // Backend result: { type:'result', run_id, explanation, step_results, artifacts } — no 'status' field
  if (type === 'result') {
    const message =
      toNonEmptyString(payload.explanation) ??
      toNonEmptyString(payload.message) ??
      fallbackMessage
    const status = payload.status === 'failed' ? ('failed' as const) : ('done' as const)
    const rawStepResults = Array.isArray(payload.step_results) ? payload.step_results : []
    const step_results: StepResult[] = rawStepResults.map((sr) => {
      const s = isRecord(sr) ? sr : {}
      return {
        step_type: toNonEmptyString(s.step_type) ?? 'unknown',
        metadata: isRecord(s.metadata) ? (s.metadata as Record<string, unknown>) : {},
      }
    })
    // Parse artifacts from execute response (Artefakte aus direktem Execute, z.B. Split-CSVs)
    const rawArtifacts = Array.isArray(payload.artifacts) ? payload.artifacts : []
    const artifacts: ArtifactRef[] = rawArtifacts
      .filter(isRecord)
      .map((a) => {
        const id = toNonEmptyString(a.artifact_id) ?? toNonEmptyString(a.id) ?? ''
        const artifactType = toNonEmptyString(a.type) ?? ''
        const label = toNonEmptyString(a.label) ?? artifactTypeToLabel(artifactType)
        const url = id && baseUrl ? `${baseUrl.replace(/\/+$/, '')}/v1/artifacts/${encodeURIComponent(id)}` : ''
        const media_type = artifactTypeToMime(artifactType)
        return { id, label, url, media_type }
      })
      .filter((a) => Boolean(a.id && a.url))
    let spec_summary: SpecSummary | undefined
    if (isRecord(payload.spec) && payload.version) {
      const rawSteps = Array.isArray((payload.spec as Record<string, unknown>).steps)
        ? ((payload.spec as Record<string, unknown>).steps as unknown[])
        : []
      spec_summary = {
        spec_version_id: toNonEmptyString(payload.version) ?? 'unknown',
        steps: rawSteps.map((s) => {
          const step = isRecord(s) ? s : {}
          return {
            step_type: toNonEmptyString(step.step_type ?? step.type) ?? 'unknown',
            enabled: typeof step.enabled === 'boolean' ? step.enabled : true,
          }
        }),
      }
    }
    const run_id = toNonEmptyString(payload.run_id) ?? undefined
    const post_run_explanation = toNonEmptyString(payload.post_run_explanation) ?? undefined
    const rawMetrics = payload.metrics
    const metrics: Record<string, number | string> | undefined =
      isRecord(rawMetrics) && Object.keys(rawMetrics).length > 0
        ? (rawMetrics as Record<string, number | string>)
        : undefined
    return {
      type: 'result',
      message,
      status,
      ...(run_id ? { run_id } : {}),
      ...(post_run_explanation ? { post_run_explanation } : {}),
      ...(step_results.length > 0 ? { step_results } : {}),
      ...(metrics ? { metrics } : {}),
      ...(artifacts.length > 0 ? { artifacts } : {}),
      ...(spec_summary ? { spec_summary } : {}),
    }
  }

  // Backend spec_updated: { type:'spec_updated', version, spec, explanation }
  if (type === 'spec_updated') {
    const message =
      toNonEmptyString(payload.explanation) ??
      toNonEmptyString(payload.message) ??
      fallbackMessage
    const version = toNonEmptyString(payload.version) ?? 'unknown'
    const rawSpec = isRecord(payload.spec) ? payload.spec : {}
    const rawSteps = Array.isArray(rawSpec.steps) ? rawSpec.steps : []
    const spec_summary: SpecSummary = {
      spec_version_id: version,
      steps: rawSteps.map((s) => {
        const step = isRecord(s) ? s : {}
        return {
          step_type: toNonEmptyString(step.step_type ?? step.type) ?? 'unknown',
          enabled: typeof step.enabled === 'boolean' ? step.enabled : true,
        }
      }),
    }
    return { type: 'spec_updated', message, spec_summary }
  }

  // Backend info: { type:'info', message } — Command-Antworten (z.B. /help)
  if (type === 'info') {
    const message = toNonEmptyString(payload.message) ?? fallbackMessage
    return { type: 'info', message }
  }

  // Backend assistant: { type:'assistant', message } — reine Textnachricht des Backends (z.B. info-Antworten)
  if (type === 'assistant') {
    const message = toNonEmptyString(payload.message) ?? fallbackMessage
    return { type: 'info', message }
  }

  // Backend error: { type:'error', message, error_code } — error_code → details
  if (type === 'error') {
    const message = toNonEmptyString(payload.message) ?? fallbackMessage
    const details =
      toNonEmptyString(payload.error_code) ??
      toNonEmptyString(payload.details) ??
      undefined
    return { type: 'error', message, ...(details ? { details } : {}) }
  }

  // Legacy session/validation error format: { error, detail, code }
  const detail = toNonEmptyString(payload.detail)
  const error = toNonEmptyString(payload.error)
  const code = payload.code

  if (detail || error || code !== undefined) {
    return {
      type: 'error',
      message: detail ?? error ?? fallbackMessage,
      details:
        typeof code === 'string' || typeof code === 'number'
          ? String(code)
          : undefined,
    }
  }

  return { type: 'error', message: fallbackMessage }
}

export async function sendRealConfirm(
  backendBaseUrl: string,
  sessionId: string,
  proposalId: string,
): Promise<ConfirmResult> {
  const baseUrl = backendBaseUrl.replace(/\/+$/, '')
  const response = await fetch(
    `${baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/confirm`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proposal_id: proposalId }),
    },
  )
  const body = await parseJsonBody(response)

  if (!response.ok) {
    const errBody = isRecord(body) ? body : {}
    const detail =
      toNonEmptyString(errBody.detail) ??
      `Confirm fehlgeschlagen (HTTP ${response.status}).`
    return { runId: null, error: detail }
  }

  if (!isRecord(body)) {
    return { runId: null, error: 'Confirm-Response konnte nicht gelesen werden.' }
  }

  const runId = toNonEmptyString(body.run_id)
  if (!runId) {
    return { runId: null, error: 'Confirm-Response enthält keine run_id.' }
  }

  let specSummary: SpecSummary | undefined
  if (isRecord(body.spec) && body.version) {
    const rawSteps = Array.isArray((body.spec as Record<string, unknown>).steps)
      ? ((body.spec as Record<string, unknown>).steps as unknown[])
      : []
    specSummary = {
      spec_version_id: toNonEmptyString(body.version) ?? 'unknown',
      steps: rawSteps.map((s) => {
        const step = isRecord(s) ? s : {}
        return {
          step_type: toNonEmptyString(step.step_type ?? step.type) ?? 'unknown',
          enabled: typeof step.enabled === 'boolean' ? step.enabled : true,
        }
      }),
    }
  }

  return { runId, ...(specSummary ? { specSummary } : {}) }
}

function artifactTypeToLabel(type: string): string {
  const labels: Record<string, string> = {
    split_train: 'Trainingsdaten (CSV)',
    split_test: 'Testdaten (CSV)',
    feature_importance: 'Feature Importance',
    ebm_global_explanation: 'EBM Global Explanation',
    correlation_filter: 'Korrelations-Filter (CSV)',
    plot_distribution: 'Verteilungsplot',
  }
  return labels[type] ?? (type || 'Artifact')
}

function artifactTypeToMime(type: string): string {
  if (type === 'split_train' || type === 'split_test') return 'text/csv'
  if (type === 'correlation_filter') return 'text/csv'
  if (type === 'feature_importance' || type === 'ebm_global_explanation' || type === 'plot_distribution') return 'image/png'
  return 'application/octet-stream'
}
