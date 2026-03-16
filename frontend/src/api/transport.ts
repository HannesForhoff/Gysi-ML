import { getFrontendEnv } from '../env'
import type {
  SendAssistantMessageInput,
  SendAssistantMessageResult,
} from './transportTypes'

import { sendMockMessage } from './mockTransport'
import { sendRealMessage } from './realTransport'

export async function sendAssistantMessage(
  input: SendAssistantMessageInput,
): Promise<SendAssistantMessageResult> {
  const env = getFrontendEnv()

  return env.useMock
    ? await sendMockMessage(input)
    : await sendRealMessage(env.backendBaseUrl, input)
}
