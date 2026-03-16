import type { AssistantResponse } from '../types'

export async function sendRealMessage(
  backendBaseUrl: string,
  userText: string,
): Promise<AssistantResponse> {
  void userText

  throw new Error(
    `Real backend transport is not implemented yet for ${backendBaseUrl}. Set VITE_GYSI_USE_MOCK=1 for Mock-Mode.`,
  )
}
