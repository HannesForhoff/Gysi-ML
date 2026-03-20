import { useEffect } from 'react'
import type { Dispatch } from 'react'

import { fetchRunStatus } from '../api/runApi'
import type { ChatAction, ChatState } from '../state/chatReducer'
import type { ArtifactRef, ChatMessage, RunStatusResponse } from '../types'

const INITIAL_INTERVAL_MS = 1_000
const MAX_INTERVAL_MS = 8_000
const LONG_RUN_THRESHOLD_MS = 120_000
const MOCK_LATENCY_MS = import.meta.env.MODE === 'test' ? 0 : 300

type PollingState = Pick<ChatState, 'ui' | 'runId' | 'sessionId' | 'transport'>

export function useRunPolling(
  dispatch: Dispatch<ChatAction>,
  state: PollingState,
): void {
  const isPolling = state.ui.type === 'run_polling'
  const runId = state.runId
  const sessionId = state.sessionId
  const useMock = state.transport.useMock
  const baseUrl = state.transport.backendBaseUrl

  useEffect(() => {
    if (!isPolling || !runId || !sessionId) return

    let cancelled = false
    let pollTimeout: ReturnType<typeof setTimeout> | undefined
    let currentInterval = INITIAL_INTERVAL_MS
    let mockCallCount = 0

    const longRunTimeout = setTimeout(() => {
      if (!cancelled) {
        dispatch({ type: 'RUN_LONG_RUNNING' })
      }
    }, LONG_RUN_THRESHOLD_MS)

    async function poll() {
      if (cancelled) return

      try {
        const result: RunStatusResponse = useMock
          ? await fetchMockRunStatus(++mockCallCount)
          : await fetchRunStatus(baseUrl, sessionId!, runId!)

        if (cancelled) return

        if (result.status === 'done' || result.status === 'failed') {
          const assistantMessage = createResultMessage(result)
          dispatch({
            type: 'RUN_POLL_SUCCEEDED',
            status: result.status,
            metrics: result.metrics,
            artifacts: result.artifacts,
            errorMessage: result.error_message,
            assistantMessage,
          })
        } else {
          dispatch({
            type: 'RUN_POLL_SUCCEEDED',
            status: result.status,
          })
          // Schedule next poll with backoff
          currentInterval = Math.min(currentInterval * 2, MAX_INTERVAL_MS)
          pollTimeout = setTimeout(() => { void poll() }, currentInterval)
        }
      } catch {
        if (cancelled) return
        dispatch({
          type: 'RUN_POLL_NETWORK_ERROR',
          errorMessage: 'Backend nicht erreichbar während Polling.',
        })
      }
    }

    pollTimeout = setTimeout(() => { void poll() }, currentInterval)

    return () => {
      cancelled = true
      if (pollTimeout !== undefined) clearTimeout(pollTimeout)
      if (longRunTimeout !== undefined) clearTimeout(longRunTimeout)
    }
  }, [isPolling, runId, sessionId, useMock, baseUrl, dispatch])
}

async function fetchMockRunStatus(callCount: number): Promise<RunStatusResponse> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS))

  if (callCount < 3) {
    return { status: 'running' }
  }

  return {
    status: 'done',
    metrics: { rmse: 123.45, r2: 0.89 },
    artifacts: [
      {
        id: 'mock-plot-1',
        label: 'Plot (Mock)',
        url: '/favicon.svg',
        media_type: 'image/svg+xml',
      },
    ],
  }
}

function createResultMessage(result: RunStatusResponse): ChatMessage {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`

  if (result.status === 'done') {
    const metricsText = result.metrics
      ? `\n\nMetrics:\n${Object.entries(result.metrics)
          .map(([k, v]) => `- ${k}: ${String(v)}`)
          .join('\n')}`
      : ''

    const artifactsText = result.artifacts
      ? `\n\nArtifacts:\n${result.artifacts.map((a: ArtifactRef) => `- ${a.label} (${a.media_type})`).join('\n')}`
      : ''

    const content = `Run abgeschlossen.${metricsText}${artifactsText}`

    return {
      id,
      role: 'assistant',
      content,
      ts: new Date().toISOString(),
      response: {
        type: 'result',
        message: 'Run abgeschlossen',
        status: 'done',
        metrics: result.metrics,
        artifacts: result.artifacts,
      },
    }
  }

  const errorMsg = result.error_message ?? 'Run fehlgeschlagen'
  return {
    id,
    role: 'assistant',
    content: errorMsg,
    ts: new Date().toISOString(),
    response: {
      type: 'result',
      message: errorMsg,
      status: 'failed',
    },
  }
}
