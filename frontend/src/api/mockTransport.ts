import type { AssistantResponse } from '../types'
import type {
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
