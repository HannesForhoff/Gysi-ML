import { describe, expect, it } from 'vitest'

import { chatReducer, createInitialChatState } from './chatReducer'
import type { ChatState } from './chatReducer'

function pendingState(): ChatState {
  return {
    ...createInitialChatState(),
    ui: { type: 'proposal_pending' },
    pendingProposalId: 'proposal-abc',
    sessionId: 'session-xyz',
  }
}

describe('chatReducer — CONFIRM_STARTED', () => {
  it('setzt isConfirming auf true', () => {
    const next = chatReducer(pendingState(), { type: 'CONFIRM_STARTED' })
    expect(next.isConfirming).toBe(true)
  })

  it('ui.type bleibt proposal_pending (kein State-Wechsel vor Response)', () => {
    const next = chatReducer(pendingState(), { type: 'CONFIRM_STARTED' })
    expect(next.ui.type).toBe('proposal_pending')
  })
})

describe('chatReducer — CONFIRM_SUCCEEDED', () => {
  it('wechselt ui.type auf run_polling', () => {
    const state: ChatState = { ...pendingState(), isConfirming: true }
    const next = chatReducer(state, { type: 'CONFIRM_SUCCEEDED', runId: 'run-001' })
    expect(next.ui.type).toBe('run_polling')
  })

  it('setzt runId', () => {
    const state: ChatState = { ...pendingState(), isConfirming: true }
    const next = chatReducer(state, { type: 'CONFIRM_SUCCEEDED', runId: 'run-001' })
    expect(next.runId).toBe('run-001')
  })

  it('setzt isConfirming zurück auf false', () => {
    const state: ChatState = { ...pendingState(), isConfirming: true }
    const next = chatReducer(state, { type: 'CONFIRM_SUCCEEDED', runId: 'run-001' })
    expect(next.isConfirming).toBe(false)
  })

  it('setzt pendingProposalId auf null', () => {
    const state: ChatState = { ...pendingState(), isConfirming: true }
    const next = chatReducer(state, { type: 'CONFIRM_SUCCEEDED', runId: 'run-001' })
    expect(next.pendingProposalId).toBeNull()
  })
})

describe('chatReducer — CONFIRM_FAILED', () => {
  it('wechselt ui.type auf validation_error', () => {
    const state: ChatState = { ...pendingState(), isConfirming: true }
    const next = chatReducer(state, {
      type: 'CONFIRM_FAILED',
      errorMessage: 'Proposal nicht gefunden',
    })
    expect(next.ui.type).toBe('validation_error')
  })

  it('setzt isConfirming zurück auf false', () => {
    const state: ChatState = { ...pendingState(), isConfirming: true }
    const next = chatReducer(state, {
      type: 'CONFIRM_FAILED',
      errorMessage: 'Fehler XYZ',
    })
    expect(next.isConfirming).toBe(false)
  })

  it('lastError enthält die Fehlermeldung', () => {
    const state: ChatState = { ...pendingState(), isConfirming: true }
    const next = chatReducer(state, {
      type: 'CONFIRM_FAILED',
      errorMessage: 'Proposal nicht gefunden',
    })
    expect(next.lastError).toBe('Proposal nicht gefunden')
  })
})
