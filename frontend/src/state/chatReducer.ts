import { getFrontendEnv } from '../env'
import type {
  ArtifactRef,
  AssistantResponse,
  ChatMessage,
  ResultResponse,
  RunStatus,
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
  pendingProposalId: string | null
  runId: string | null
  isConfirming: boolean
  isLongRunning: boolean
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
  | { type: 'HEALTH_CHECK_FAILED' }
  | { type: 'HEALTH_CHECK_RECOVERED' }
  | { type: 'SPEC_SUMMARY_LOADED'; specSummary: SpecSummary }
  | { type: 'CONFIRM_STARTED' }
  | { type: 'CONFIRM_SUCCEEDED'; runId: string }
  | { type: 'CONFIRM_FAILED'; errorMessage: string }
  | {
      type: 'RUN_POLL_SUCCEEDED'
      status: RunStatus
      metrics?: Record<string, number | string>
      artifacts?: ArtifactRef[]
      errorMessage?: string
      assistantMessage?: ChatMessage
    }
  | { type: 'RUN_POLL_NETWORK_ERROR'; errorMessage: string }
  | { type: 'RUN_LONG_RUNNING' }

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
    pendingProposalId: null,
    runId: null,
    isConfirming: false,
    isLongRunning: false,
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
    case 'spec_updated':
      return { type: 'idle' }
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
        // Sofortiges visuelles Feedback: alter Proposal wird als "nicht bestätigt" markiert,
        // sobald der Nutzer eine neue Nachricht sendet.
        pendingProposalId: state.ui.type === 'proposal_pending' ? null : state.pendingProposalId,
      }

    case 'SEND_REQUEST_SUCCEEDED': {
      const { response } = action

      const specSummary =
        response.type === 'proposal' || response.type === 'result'
          ? response.spec_summary ?? state.specSummary
          : response.type === 'spec_updated'
            ? response.spec_summary
            : state.specSummary

      const artifacts =
        response.type === 'result' && response.artifacts
          ? response.artifacts
          : state.artifacts

      const lastRun = response.type === 'result' ? response : state.lastRun

      const pendingProposalId =
        response.type === 'proposal'
          ? (response.proposal_id ?? null)
          : null

      return {
        ...state,
        ui: nextUiStateForResponse(response),
        messages: [...state.messages, action.assistantMessage],
        sessionId: action.sessionId,
        specSummary,
        artifacts,
        lastRun,
        lastError: null,
        pendingProposalId,
      }
    }

    case 'SEND_REQUEST_FAILED':
      return {
        ...state,
        ui: { type: 'backend_unreachable' },
        messages: [...state.messages, action.assistantMessage],
        lastError: action.errorMessage,
      }

    case 'HEALTH_CHECK_FAILED':
      // Kein Override wenn aktiver Request läuft
      if (state.ui.type === 'sending_message' || state.ui.type === 'backend_unreachable') {
        return state
      }
      return { ...state, ui: { type: 'backend_unreachable' } }

    case 'HEALTH_CHECK_RECOVERED':
      if (state.ui.type !== 'backend_unreachable') {
        return state
      }
      return { ...state, ui: { type: 'idle' } }

    case 'SPEC_SUMMARY_LOADED':
      return { ...state, specSummary: action.specSummary }

    case 'CONFIRM_STARTED':
      return { ...state, isConfirming: true }

    case 'CONFIRM_SUCCEEDED':
      return {
        ...state,
        isConfirming: false,
        runId: action.runId,
        pendingProposalId: null,
        ui: { type: 'run_polling' },
      }

    case 'CONFIRM_FAILED':
      return {
        ...state,
        isConfirming: false,
        lastError: action.errorMessage,
        ui: { type: 'validation_error' },
      }

    case 'RUN_POLL_SUCCEEDED': {
      if (action.status === 'done') {
        const lastRun: ResultResponse = {
          type: 'result',
          message: 'Run abgeschlossen',
          status: 'done',
          metrics: action.metrics,
          artifacts: action.artifacts,
        }
        return {
          ...state,
          ui: { type: 'run_done' },
          lastRun,
          artifacts: action.artifacts ?? state.artifacts,
          runId: null,
          isLongRunning: false,
          ...(action.assistantMessage
            ? { messages: [...state.messages, action.assistantMessage] }
            : {}),
        }
      }

      if (action.status === 'failed') {
        const errorMsg = action.errorMessage ?? 'Run fehlgeschlagen'
        const lastRun: ResultResponse = {
          type: 'result',
          message: errorMsg,
          status: 'failed',
        }
        return {
          ...state,
          ui: { type: 'run_failed' },
          lastRun,
          lastError: errorMsg,
          runId: null,
          isLongRunning: false,
          ...(action.assistantMessage
            ? { messages: [...state.messages, action.assistantMessage] }
            : {}),
        }
      }

      // running | queued → keep polling
      return state
    }

    case 'RUN_POLL_NETWORK_ERROR':
      return {
        ...state,
        ui: { type: 'backend_unreachable' },
        lastError: action.errorMessage,
        runId: null,
        isLongRunning: false,
      }

    case 'RUN_LONG_RUNNING':
      if (state.ui.type !== 'run_polling') return state
      return { ...state, isLongRunning: true }
  }
}
