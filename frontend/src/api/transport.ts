import { getFrontendEnv } from '../env'
import type {
  ConfirmInput,
  ConfirmResult,
  SendAssistantMessageInput,
  SendAssistantMessageResult,
} from './transportTypes'

import { sendMockConfirm, sendMockMessage } from './mockTransport'
import { sendRealConfirm, sendRealMessage } from './realTransport'

export async function sendAssistantMessage(
  input: SendAssistantMessageInput,
): Promise<SendAssistantMessageResult> {
  const env = getFrontendEnv()

  return env.useMock
    ? await sendMockMessage(input)
    : await sendRealMessage(env.backendBaseUrl, input)
}

export async function confirmProposal(input: ConfirmInput): Promise<ConfirmResult> {
  const env = getFrontendEnv()
  return env.useMock
    ? await sendMockConfirm(input.proposalId)
    : await sendRealConfirm(env.backendBaseUrl, input.sessionId, input.proposalId)
}
