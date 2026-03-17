import { describe, expect, it } from 'vitest'

import {
  chatReducer,
  createInitialChatState,
} from './chatReducer'
import type { ChatState } from './chatReducer'

function stateWith(uiType: ChatState['ui']['type']): ChatState {
  return { ...createInitialChatState(), ui: { type: uiType } as ChatState['ui'] }
}

describe('chatReducer — HEALTH_CHECK_FAILED', () => {
  it('idle → backend_unreachable', () => {
    const next = chatReducer(stateWith('idle'), { type: 'HEALTH_CHECK_FAILED' })
    expect(next.ui.type).toBe('backend_unreachable')
  })

  it('backend_unreachable → bleibt backend_unreachable (Idempotenz)', () => {
    const next = chatReducer(stateWith('backend_unreachable'), {
      type: 'HEALTH_CHECK_FAILED',
    })
    expect(next.ui.type).toBe('backend_unreachable')
  })

  it('sending_message → kein Override; bleibt sending_message', () => {
    const next = chatReducer(stateWith('sending_message'), {
      type: 'HEALTH_CHECK_FAILED',
    })
    expect(next.ui.type).toBe('sending_message')
  })
})

describe('chatReducer — HEALTH_CHECK_RECOVERED', () => {
  it('backend_unreachable → idle', () => {
    const next = chatReducer(stateWith('backend_unreachable'), {
      type: 'HEALTH_CHECK_RECOVERED',
    })
    expect(next.ui.type).toBe('idle')
  })

  it('idle → bleibt idle (Idempotenz)', () => {
    const next = chatReducer(stateWith('idle'), { type: 'HEALTH_CHECK_RECOVERED' })
    expect(next.ui.type).toBe('idle')
  })
})

describe('chatReducer — SPEC_SUMMARY_LOADED', () => {
  it('überschreibt specSummary im State', () => {
    const summary = {
      spec_version_id: 'v1',
      steps: [{ step_type: 'dedup', enabled: true }],
    }
    const next = chatReducer(createInitialChatState(), {
      type: 'SPEC_SUMMARY_LOADED',
      specSummary: summary,
    })
    expect(next.specSummary).toEqual(summary)
  })
})
