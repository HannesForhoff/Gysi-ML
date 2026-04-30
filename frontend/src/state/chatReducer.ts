import { getFrontendEnv } from '../env'
import type {
  ArtifactRef,
  AssistantResponse,
  ChatMessage,
  ResultResponse,
  RunStatus,
  SpecSummary,
  VersionTree,
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
  specHistory: VersionTree | null
  lastRun: ResultResponse | null
  artifacts: ArtifactRef[]
  lastError: string | null
  pendingProposalId: string | null
  runId: string | null
  isConfirming: boolean
  isLongRunning: boolean
  llmModel: string | null
  activeTab: 'chat' | 'data' | 'info'
  activeDataRunId: string | null
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
  | { type: 'HEALTH_CHECK_RECOVERED'; llmModel?: string | null }
  | { type: 'SPEC_SUMMARY_LOADED'; specSummary: SpecSummary }
  | { type: 'CONFIRM_STARTED' }
  | { type: 'CONFIRM_SUCCEEDED'; runId: string; specSummary?: SpecSummary }
  | { type: 'CONFIRM_FAILED'; errorMessage: string }
  | {
      type: 'RUN_POLL_SUCCEEDED'
      status: RunStatus
      metrics?: Record<string, number | string>
      artifacts?: ArtifactRef[]
      errorMessage?: string
      assistantMessage?: ChatMessage
      step_results?: StepResult[]
    }
  | { type: 'RUN_POLL_NETWORK_ERROR'; errorMessage: string }
  | { type: 'RUN_LONG_RUNNING' }
  | { type: 'SPEC_TREE_LOADED'; specTree: VersionTree }
  | { type: 'ROLLBACK_SUCCEEDED'; infoMessage: ChatMessage; specTree: VersionTree; specSummary: SpecSummary | null; activeDataRunId: string | null }
  | { type: 'ROLLBACK_FAILED'; errorMessage: string; errorChatMessage: ChatMessage }
  | { type: 'SET_ACTIVE_TAB'; tab: 'chat' | 'data' | 'info' }

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    'Hallo! Ich bin **Gysi**, dein ML-Assistent für den Bike-Sharing-Datensatz.\n\n' +
    'Ich helfe dir dabei, die Daten Schritt für Schritt zu verstehen und ein Machine-Learning-Modell aufzubauen. ' +
    'Beschreibe einfach auf Deutsch, was du machen möchtest — zum Beispiel:\n\n' +
    '- *"Entferne Duplikate aus dem Datensatz"*\n' +
    '- *"Imputiere fehlende Werte in windspeed mit dem Median"*\n' +
    '- *"Führe einen Train-Test-Split durch"*\n\n' +
    'Tipp: Gib `/help` ein, um alle verfügbaren Commands, Steps und Funktionen aufzulisten.\n\n' +
    'Womit möchtest du beginnen?',
  ts: new Date().toISOString(),
}

export function createInitialChatState(): ChatState {
  const env = getFrontendEnv()

  return {
    ui: { type: 'idle' },
    messages: [WELCOME_MESSAGE],
    transport: { useMock: env.useMock, backendBaseUrl: env.backendBaseUrl },
    sessionId: null,
    specSummary: null,
    specHistory: null,
    lastRun: null,
    artifacts: [],
    lastError: null,
    pendingProposalId: null,
    runId: null,
    isConfirming: false,
    isLongRunning: false,
    llmModel: null,
    activeTab: 'chat',
    activeDataRunId: null,
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
    case 'info':
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
          ? [
              ...state.artifacts,
              ...response.artifacts.filter(
                (a) => !state.artifacts.some((sa) => sa.id === a.id),
              ),
            ]
          : state.artifacts

      const lastRun = response.type === 'result' ? response : state.lastRun

      const pendingProposalId =
        response.type === 'proposal'
          ? (response.proposal_id ?? null)
          : null

      // Bei direkter Ausführung (action:execute via message-Pfad) ist die Run-ID
      // im result enthalten — activeDataRunId direkt setzen (kein Polling-Zyklus).
      const activeDataRunId =
        response.type === 'result' && response.run_id
          ? response.run_id
          : state.activeDataRunId

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
        activeDataRunId,
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
        // Auch im Nicht-Fehlerfall llmModel aktualisieren
        if (action.llmModel !== undefined && action.llmModel !== state.llmModel) {
          return { ...state, llmModel: action.llmModel }
        }
        return state
      }
      return {
        ...state,
        ui: { type: 'idle' },
        ...(action.llmModel !== undefined ? { llmModel: action.llmModel } : {}),
      }

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
        ...(action.specSummary ? { specSummary: action.specSummary } : {}),
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
          step_results: action.step_results,
        }
        return {
          ...state,
          ui: { type: 'run_done' },
          lastRun,
          artifacts: action.artifacts
            ? [
                ...state.artifacts,
                ...action.artifacts.filter(
                  (a) => !state.artifacts.some((sa) => sa.id === a.id),
                ),
              ]
            : state.artifacts,
          activeDataRunId: state.runId,
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

    case 'SPEC_TREE_LOADED':
      return { ...state, specHistory: action.specTree }

    case 'ROLLBACK_SUCCEEDED':
      return {
        ...state,
        ui: { type: 'idle' },
        specHistory: action.specTree,
        specSummary: action.specSummary ?? state.specSummary,
        messages: [...state.messages, action.infoMessage],
        lastError: null,
        activeDataRunId: action.activeDataRunId,
      }

    case 'ROLLBACK_FAILED':
      return {
        ...state,
        ui: { type: 'validation_error' },
        lastError: action.errorMessage,
        messages: [...state.messages, action.errorChatMessage],
      }

    case 'SET_ACTIVE_TAB':
      return { ...state, activeTab: action.tab }
  }
}
