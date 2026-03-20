import { describe, expect, it } from 'vitest'

import { chatReducer, createInitialChatState } from './chatReducer'
import type { ChatState } from './chatReducer'
import type { ArtifactRef, ChatMessage } from '../types'

function pollingState(overrides?: Partial<ChatState>): ChatState {
  return {
    ...createInitialChatState(),
    ui: { type: 'run_polling' },
    runId: 'run-001',
    sessionId: 'sess-1',
    ...overrides,
  }
}

const dummyAssistantMessage: ChatMessage = {
  id: 'msg-result',
  role: 'assistant',
  content: 'Run abgeschlossen.',
  ts: new Date().toISOString(),
}

const mockArtifacts: ArtifactRef[] = [
  { id: 'plot-1', label: 'Plot', url: '/v1/artifacts/plot-1', media_type: 'image/svg+xml' },
]

describe('chatReducer — RUN_POLL_SUCCEEDED (done)', () => {
  it('ui wechselt zu run_done', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
      metrics: { rmse: 1.23 },
      artifacts: mockArtifacts,
      assistantMessage: dummyAssistantMessage,
    })
    expect(next.ui.type).toBe('run_done')
  })

  it('setzt lastRun mit metrics und artifacts', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
      metrics: { rmse: 1.23 },
      artifacts: mockArtifacts,
    })
    expect(next.lastRun).toEqual({
      type: 'result',
      message: 'Run abgeschlossen',
      status: 'done',
      metrics: { rmse: 1.23 },
      artifacts: mockArtifacts,
    })
  })

  it('aktualisiert artifacts im State', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
      artifacts: mockArtifacts,
    })
    expect(next.artifacts).toEqual(mockArtifacts)
  })

  it('behält alte artifacts wenn keine neuen vorhanden', () => {
    const oldArtifacts: ArtifactRef[] = [
      { id: 'old', label: 'Old', url: '/old', media_type: 'text/plain' },
    ]
    const next = chatReducer(pollingState({ artifacts: oldArtifacts }), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
    })
    expect(next.artifacts).toEqual(oldArtifacts)
  })

  it('setzt runId auf null', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
    })
    expect(next.runId).toBeNull()
  })

  it('setzt isLongRunning auf false', () => {
    const next = chatReducer(pollingState({ isLongRunning: true }), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
    })
    expect(next.isLongRunning).toBe(false)
  })

  it('fügt assistantMessage zu messages hinzu wenn vorhanden', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
      assistantMessage: dummyAssistantMessage,
    })
    expect(next.messages).toContain(dummyAssistantMessage)
  })

  it('ändert messages nicht wenn keine assistantMessage', () => {
    const state = pollingState()
    const next = chatReducer(state, {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'done',
    })
    expect(next.messages).toEqual(state.messages)
  })
})

describe('chatReducer — RUN_POLL_SUCCEEDED (failed)', () => {
  it('ui wechselt zu run_failed', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'failed',
      errorMessage: 'Out of memory',
    })
    expect(next.ui.type).toBe('run_failed')
  })

  it('setzt lastRun mit failed status', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'failed',
      errorMessage: 'Crash',
    })
    expect(next.lastRun?.status).toBe('failed')
    expect(next.lastRun?.message).toBe('Crash')
  })

  it('setzt lastError', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'failed',
      errorMessage: 'Crash',
    })
    expect(next.lastError).toBe('Crash')
  })

  it('verwendet Fallback wenn kein errorMessage', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'failed',
    })
    expect(next.lastError).toBe('Run fehlgeschlagen')
  })

  it('setzt runId auf null', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'failed',
    })
    expect(next.runId).toBeNull()
  })

  it('fügt assistantMessage zu messages hinzu', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'failed',
      assistantMessage: dummyAssistantMessage,
    })
    expect(next.messages).toContain(dummyAssistantMessage)
  })
})

describe('chatReducer — RUN_POLL_SUCCEEDED (running/queued)', () => {
  it('State bleibt unverändert bei running', () => {
    const state = pollingState()
    const next = chatReducer(state, {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'running',
    })
    expect(next).toBe(state)
  })

  it('State bleibt unverändert bei queued', () => {
    const state = pollingState()
    const next = chatReducer(state, {
      type: 'RUN_POLL_SUCCEEDED',
      status: 'queued',
    })
    expect(next).toBe(state)
  })
})

describe('chatReducer — RUN_POLL_NETWORK_ERROR', () => {
  it('ui wechselt zu backend_unreachable', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_NETWORK_ERROR',
      errorMessage: 'Network error',
    })
    expect(next.ui.type).toBe('backend_unreachable')
  })

  it('setzt lastError', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_NETWORK_ERROR',
      errorMessage: 'Network error',
    })
    expect(next.lastError).toBe('Network error')
  })

  it('setzt runId auf null', () => {
    const next = chatReducer(pollingState(), {
      type: 'RUN_POLL_NETWORK_ERROR',
      errorMessage: 'err',
    })
    expect(next.runId).toBeNull()
  })

  it('setzt isLongRunning auf false', () => {
    const next = chatReducer(pollingState({ isLongRunning: true }), {
      type: 'RUN_POLL_NETWORK_ERROR',
      errorMessage: 'err',
    })
    expect(next.isLongRunning).toBe(false)
  })
})

describe('chatReducer — RUN_LONG_RUNNING', () => {
  it('setzt isLongRunning auf true wenn ui === run_polling', () => {
    const next = chatReducer(pollingState(), { type: 'RUN_LONG_RUNNING' })
    expect(next.isLongRunning).toBe(true)
  })

  it('ignoriert wenn ui !== run_polling', () => {
    const state = { ...createInitialChatState(), ui: { type: 'idle' } as const }
    const next = chatReducer(state, { type: 'RUN_LONG_RUNNING' })
    expect(next.isLongRunning).toBe(false)
    expect(next).toBe(state)
  })
})
