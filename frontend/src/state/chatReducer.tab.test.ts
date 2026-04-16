import { describe, expect, it } from 'vitest'

import { chatReducer, createInitialChatState } from './chatReducer'
import type { ChatState } from './chatReducer'

function runPollingState(): ChatState {
  return {
    ...createInitialChatState(),
    ui: { type: 'run_polling' },
    sessionId: 'session-xyz',
    runId: 'run-001',
  }
}

// ─────────────────────────────────────────────────────────
// Initial State
// ─────────────────────────────────────────────────────────

describe('createInitialChatState — Tab-Felder', () => {
  it('activeTab startet auf "chat"', () => {
    expect(createInitialChatState().activeTab).toBe('chat')
  })

  it('activeDataRunId startet auf null', () => {
    expect(createInitialChatState().activeDataRunId).toBeNull()
  })
})

// ─────────────────────────────────────────────────────────
// SET_ACTIVE_TAB
// ─────────────────────────────────────────────────────────

describe('chatReducer — SET_ACTIVE_TAB', () => {
  it('wechselt zu "chat" immer, auch ohne activeDataRunId', () => {
    const state: ChatState = { ...createInitialChatState(), activeTab: 'data', activeDataRunId: 'run-001' }
    const next = chatReducer(state, { type: 'SET_ACTIVE_TAB', tab: 'chat' })
    expect(next.activeTab).toBe('chat')
  })

  it('wechselt zu "data" wenn activeDataRunId gesetzt ist', () => {
    const state: ChatState = { ...createInitialChatState(), activeDataRunId: 'run-001' }
    const next = chatReducer(state, { type: 'SET_ACTIVE_TAB', tab: 'data' })
    expect(next.activeTab).toBe('data')
  })

  it('blockiert Wechsel zu "data" wenn activeDataRunId null ist', () => {
    const state: ChatState = { ...createInitialChatState(), activeDataRunId: null }
    const next = chatReducer(state, { type: 'SET_ACTIVE_TAB', tab: 'data' })
    expect(next.activeTab).toBe('chat')
  })

  it('gibt unverändertes State-Objekt zurück wenn Guard greift', () => {
    const state: ChatState = { ...createInitialChatState(), activeDataRunId: null }
    const next = chatReducer(state, { type: 'SET_ACTIVE_TAB', tab: 'data' })
    expect(next).toBe(state)
  })

  it('ändert kein anderes State-Feld', () => {
    const state: ChatState = { ...createInitialChatState(), activeDataRunId: 'run-001' }
    const next = chatReducer(state, { type: 'SET_ACTIVE_TAB', tab: 'data' })
    expect(next.messages).toBe(state.messages)
    expect(next.sessionId).toBe(state.sessionId)
    expect(next.activeDataRunId).toBe(state.activeDataRunId)
  })
})

// ─────────────────────────────────────────────────────────
// RUN_POLL_SUCCEEDED → activeDataRunId
// ─────────────────────────────────────────────────────────

describe('chatReducer — RUN_POLL_SUCCEEDED setzt activeDataRunId', () => {
  it('setzt activeDataRunId auf state.runId wenn status "done"', () => {
    const state = runPollingState() // runId: 'run-001'
    const next = chatReducer(state, { type: 'RUN_POLL_SUCCEEDED', status: 'done' })
    expect(next.activeDataRunId).toBe('run-001')
  })

  it('setzt runId danach auf null', () => {
    const state = runPollingState()
    const next = chatReducer(state, { type: 'RUN_POLL_SUCCEEDED', status: 'done' })
    expect(next.runId).toBeNull()
  })

  it('verändert activeDataRunId NICHT wenn status "failed"', () => {
    const state: ChatState = { ...runPollingState(), activeDataRunId: 'previous-run' }
    const next = chatReducer(state, { type: 'RUN_POLL_SUCCEEDED', status: 'failed' })
    expect(next.activeDataRunId).toBe('previous-run')
  })

  it('verändert activeDataRunId NICHT wenn status "running"', () => {
    const state: ChatState = { ...runPollingState(), activeDataRunId: 'previous-run' }
    const next = chatReducer(state, { type: 'RUN_POLL_SUCCEEDED', status: 'running' })
    expect(next.activeDataRunId).toBe('previous-run')
  })

  it('activeDataRunId bleibt null wenn runId schon null war (edge case)', () => {
    const state: ChatState = { ...runPollingState(), runId: null }
    const next = chatReducer(state, { type: 'RUN_POLL_SUCCEEDED', status: 'done' })
    expect(next.activeDataRunId).toBeNull()
  })
})
