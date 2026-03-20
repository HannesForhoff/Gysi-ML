import { describe, expect, it } from 'vitest'
import { chatReducer, createInitialChatState } from './chatReducer'
import type { ChatState } from './chatReducer'
import type { ChatMessage } from '../types'

function makeProposalPendingState(): ChatState {
  return {
    ...createInitialChatState(),
    ui: { type: 'proposal_pending' },
    pendingProposalId: 'mock-proposal-001',
    sessionId: 'session-abc',
  }
}

const dummyUserMessage: ChatMessage = {
  id: 'u1',
  role: 'user',
  content: 'modifizieren',
  ts: new Date().toISOString(),
}

describe('SEND_REQUEST_STARTED — Modify-Flow', () => {
  it('löscht pendingProposalId wenn ui.type === proposal_pending', () => {
    const state = makeProposalPendingState()
    const next = chatReducer(state, {
      type: 'SEND_REQUEST_STARTED',
      userMessage: dummyUserMessage,
    })
    expect(next.pendingProposalId).toBeNull()
    expect(next.ui.type).toBe('sending_message')
  })

  it('behält pendingProposalId wenn ui.type !== proposal_pending', () => {
    const state = {
      ...createInitialChatState(),
      ui: { type: 'idle' } as const,
      pendingProposalId: 'some-id',
    }
    const next = chatReducer(state, {
      type: 'SEND_REQUEST_STARTED',
      userMessage: dummyUserMessage,
    })
    expect(next.pendingProposalId).toBe('some-id')
  })

  it('fügt userMessage zu messages hinzu', () => {
    const state = makeProposalPendingState()
    const next = chatReducer(state, {
      type: 'SEND_REQUEST_STARTED',
      userMessage: dummyUserMessage,
    })
    expect(next.messages).toContain(dummyUserMessage)
  })
})
