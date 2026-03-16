import { getFrontendEnv } from '../env'
import type {
  ArtifactRef,
  AssistantResponse,
  ChatMessage,
  ResultResponse,
  SpecSummary,
} from '../types'

export type UiState =
  | { type: 'idle' }
  | { type: 'sending_message' }
  | { type: 'proposal_pending' }
  | { type: 'run_polling' }
  | { type: 'run_done' }
  | { type: 'run_failed' }
  | { type: 'validation_error' }
  | { type: 'backend_unreachable' }

export interface TransportInfo {
  useMock: boolean
  backendBaseUrl: string
}

export interface ChatState {
  ui: UiState
  messages: ChatMessage[]
  transport: TransportInfo
  sessionId: string | null
  specSummary: SpecSummary | null
  lastRun: ResultResponse | null
  artifacts: ArtifactRef[]
  lastError: string | null
}

export type ChatAction =
  | { type: 'SEND_REQUEST_STARTED'; userMessage: ChatMessage }
  | {
      type: 'SEND_REQUEST_SUCCEEDED'
      assistantMessage: ChatMessage
      sessionId: string | null
      response: AssistantResponse
    }
  | {
      type: 'SEND_REQUEST_FAILED'
      assistantMessage: ChatMessage
      errorMessage: string
    }

export function createInitialChatState(): ChatState {
  const env = getFrontendEnv()

  return {
    ui: { type: 'idle' },
    messages: [],
    transport: { useMock: env.useMock, backendBaseUrl: env.backendBaseUrl },
    sessionId: null,
    specSummary: null,
    lastRun: null,
    artifacts: [],
    lastError: null,
  }
}

function nextUiStateForResponse(response: AssistantResponse): UiState {
  switch (response.type) {
    case 'proposal':
      return { type: 'proposal_pending' }
    case 'result':
      return response.status === 'done'
        ? { type: 'run_done' }
        : { type: 'run_failed' }
    case 'error':
      return { type: 'validation_error' }
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SEND_REQUEST_STARTED':
      return {
        ...state,
        ui: { type: 'sending_message' },
        messages: [...state.messages, action.userMessage],
        lastError: null,
      }

    case 'SEND_REQUEST_SUCCEEDED': {
      const { response } = action

      const specSummary =
        response.type === 'proposal' || response.type === 'result'
          ? response.spec_summary ?? state.specSummary
          : state.specSummary

      const artifacts =
        response.type === 'result' && response.artifacts
          ? response.artifacts
          : state.artifacts

      const lastRun = response.type === 'result' ? response : state.lastRun

      return {
        ...state,
        ui: nextUiStateForResponse(response),
        messages: [...state.messages, action.assistantMessage],
        sessionId: action.sessionId,
        specSummary,
        artifacts,
        lastRun,
        lastError: null,
      }
    }

    case 'SEND_REQUEST_FAILED':
      return {
        ...state,
        ui: { type: 'backend_unreachable' },
        messages: [...state.messages, action.assistantMessage],
        lastError: action.errorMessage,
      }
  }
}
