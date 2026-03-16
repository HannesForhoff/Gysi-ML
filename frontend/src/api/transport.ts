import { getFrontendEnv } from '../env'
import type { AssistantResponse } from '../types'

import { sendMockMessage } from './mockTransport'
import { sendRealMessage } from './realTransport'

export async function sendAssistantMessage(
  userText: string,
): Promise<AssistantResponse> {
  const env = getFrontendEnv()

  return env.useMock
    ? await sendMockMessage(userText)
    : await sendRealMessage(env.backendBaseUrl, userText)
}
