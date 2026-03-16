import type { AssistantResponse } from '../types'

export interface SendAssistantMessageInput {
  userText: string
  sessionId: string | null
}

export interface SendAssistantMessageResult {
  sessionId: string | null
  response: AssistantResponse
}
