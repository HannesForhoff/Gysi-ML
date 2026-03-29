import { describe, expect, it } from 'vitest'

import { chatReducer, createInitialChatState } from './chatReducer'
import type { ChatState } from './chatReducer'
import type { AssistantResponse, ChatMessage, SpecSummary } from '../types'

function makeAssistantMessage(): ChatMessage {
  return {
    id: 'msg-1',
    role: 'assistant',
    content: 'Spec aktualisiert (Mock): Preprocessing auf v1 rückgesetzt.',
    ts: new Date().toISOString(),
  }
}

const SPEC_UPDATED_RESPONSE: AssistantResponse = {
  type: 'spec_updated',
  message: 'Spec aktualisiert (Mock): Preprocessing auf v1 rückgesetzt.',
  spec_summary: {
    spec_version_id: 'mock-spec-undo-v1',
    steps: [
      { step_type: 'load_csv', enabled: true },
      { step_type: 'train_model', enabled: false },
    ],
  },
}

describe('chatReducer — SEND_REQUEST_SUCCEEDED mit spec_updated', () => {
  it('setzt ui.type auf idle', () => {
    const next = chatReducer(createInitialChatState(), {
      type: 'SEND_REQUEST_SUCCEEDED',
      assistantMessage: makeAssistantMessage(),
      sessionId: 'mock',
      response: SPEC_UPDATED_RESPONSE,
    })
    expect(next.ui.type).toBe('idle')
  })

  it('aktualisiert specSummary aus response.spec_summary', () => {
    const next = chatReducer(createInitialChatState(), {
      type: 'SEND_REQUEST_SUCCEEDED',
      assistantMessage: makeAssistantMessage(),
      sessionId: 'mock',
      response: SPEC_UPDATED_RESPONSE,
    })
    expect(next.specSummary).toEqual(SPEC_UPDATED_RESPONSE.spec_summary)
  })

  it('überschreibt vorherige specSummary', () => {
    const initialSummary: SpecSummary = {
      spec_version_id: 'v0',
      steps: [{ step_type: 'old_step', enabled: true }],
    }
    const stateWithSummary: ChatState = {
      ...createInitialChatState(),
      specSummary: initialSummary,
    }
    const next = chatReducer(stateWithSummary, {
      type: 'SEND_REQUEST_SUCCEEDED',
      assistantMessage: makeAssistantMessage(),
      sessionId: 'mock',
      response: SPEC_UPDATED_RESPONSE,
    })
    expect(next.specSummary?.spec_version_id).toBe('mock-spec-undo-v1')
  })

  it('fügt assistantMessage zur messages-Liste hinzu', () => {
    const next = chatReducer(createInitialChatState(), {
      type: 'SEND_REQUEST_SUCCEEDED',
      assistantMessage: makeAssistantMessage(),
      sessionId: 'mock',
      response: SPEC_UPDATED_RESPONSE,
    })
    expect(next.messages).toHaveLength(2) // welcome + new assistant message
    expect(next.messages[1].content).toBe(
      'Spec aktualisiert (Mock): Preprocessing auf v1 rückgesetzt.',
    )
  })
})
