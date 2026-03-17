import type { AssistantResponse } from '../types'
import type {
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
      ),
    }
  }

  return {
    sessionId,
    response: toAssistantResponse(
      messageBody,
      'Backend response could not be interpreted.',
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
      const paramsSummary = params
        ? Object.entries(params)
            .map(([k, v]) => `${k}=${String(v)}`)
            .join(', ')
        : (toNonEmptyString(step.parameters_summary) ?? undefined)
      return {
        step_type: stepType,
        ...(typeof step.enabled === 'boolean' ? { enabled: step.enabled } : {}),
        ...(paramsSummary ? { parameters_summary: paramsSummary } : {}),
      }
    })
    return { type: 'proposal', message, steps }
  }

  // Backend result: { type:'result', run_id, explanation } — no 'status' field
  if (type === 'result') {
    const message =
      toNonEmptyString(payload.explanation) ??
      toNonEmptyString(payload.message) ??
      fallbackMessage
    const status = payload.status === 'failed' ? ('failed' as const) : ('done' as const)
    return { type: 'result', message, status }
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
