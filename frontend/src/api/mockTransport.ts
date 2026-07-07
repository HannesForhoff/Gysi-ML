import type { AssistantResponse } from '../types'
import type {
  ConfirmResult,
  SendAssistantMessageInput,
  SendAssistantMessageResult,
} from './transportTypes'

import proposalFixture from '../fixtures/proposal.json'
import resultFixture from '../fixtures/result.json'
import errorFixture from '../fixtures/error.json'

const MOCK_LATENCY_MS = import.meta.env.MODE === 'test' ? 0 : 250

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function pickFixture(userText: string): AssistantResponse {
  const text = userText.trim().toLowerCase()

  if (
    text.includes('undo') ||
    text.includes('rückgängig') ||
    text.includes('revert') ||
    text.includes('rollback') ||
    text.includes('berichtigen') ||
    text.includes('korrigieren')
  ) {
    return {
      type: 'info',
      message:
        'Zu früheren Versionen kannst du nur manuell über den Versionsbaum im Tree zurückgehen. Der Chat kann keinen Rollback auslösen und bereits durchgeführte Schritte nicht nachträglich berichtigen.',
    }
  }
  // NEU: Modifizierungs-Keywords → neuer Proposal (simuliert Modify-Flow)
  if (text.includes('ändern') || text.includes('modifizieren') || text.includes('modify')) {
    return proposalFixture as AssistantResponse
  }
  if (text.includes('proposal') || text.includes('vorschlag')) {
    return proposalFixture as AssistantResponse
  }

  if (text.includes('error') || text.includes('fehler') || text.includes('fail')) {
    return errorFixture as AssistantResponse
  }

  return resultFixture as AssistantResponse
}

export async function sendMockMessage(
  input: SendAssistantMessageInput,
): Promise<SendAssistantMessageResult> {
  await sleep(MOCK_LATENCY_MS)

  return {
    sessionId: input.sessionId ?? 'mock',
    response: pickFixture(input.userText),
  }
}

export async function sendMockConfirm(_proposalId: string): Promise<ConfirmResult> {
  await sleep(MOCK_LATENCY_MS)
  return { runId: 'mock-run-001' }
}
