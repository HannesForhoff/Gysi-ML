import { getFrontendEnv } from '../env'
import type {
  ArtifactRef,
  AssistantResponse,
  ChatMessage,
  ResultResponse,
  RunStatus,
  SpecSummary,
  StepResult,
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
  /** Metriken pro Spec-Version, z.B. { 'v3': { rmse: 0.12, r2: 0.88 } } */
  versionMetrics: Record<string, Record<string, number | string>>
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
    'Hallo! Ich bin **Gysi**, dein ML-Assistent für den Bike-Sharing-Datensatz. 🚲\n\n' +
    'Du brauchst keine Vorkenntnisse in Data Science oder Machine Learning — ' +
    'beschreib einfach auf Deutsch, was du möchtest. Ich schlage konkrete Schritte vor, erkläre sie ' +
    'und führe sie erst nach deiner Bestätigung deterministisch im Backend aus.\n\n' +
    '**📊 Der Datensatz:** Tägliche Fahrrad-Verleihdaten (u. a. `season`, `weathersit`, `temp`, `hum`, ' +
    '`windspeed`, `casual`, `registered`) mit `cnt` (Anzahl Ausleihen) als Zielgröße. Mit `/overview` siehst du ' +
    'Spalten, Datentypen und fehlende Werte im Detail.\n\n' +
    '**🎯 Ziel:** Schritt für Schritt eine nachvollziehbare Pipeline aufbauen — von der Datenbereinigung ' +
    '(Preprocessing) über das Training eines Modells bis zur Erklärung der Ergebnisse:\n\n' +
    '- **Preprocessing** — Duplikate entfernen, fehlende Werte imputieren, Encoding, Ausreißer behandeln, Zeitfeatures, Train/Test-Split ...\n' +
    '- **Modellierung** — Decision Tree, lineare Regression, EBM oder CatBoost-Feature-Selection trainieren\n' +
    '- **Auswertung** — Metriken, Plots und Runs vergleichen, bei Bedarf zu einer früheren Pipeline-Version zurückspringen\n\n' +
    '**🖥️ So ist die Oberfläche aufgebaut:**\n\n' +
    '- **Chat** (hier) — Unterhaltung mit Vorschlägen, Bestätigungen und Erklärungen\n' +
    '- **Daten** — Tabellenansicht der Roh- bzw. aktuellen Trainings-/Testdaten inkl. Spaltenstatistiken\n' +
    '- **Artefakte & Steps** — Ergebnisse, Metriken und Plots des letzten Runs sowie Details zu jedem Pipeline-Schritt\n' +
    '- **Spec-Verlauf** (rechte Seitenleiste) — Versionsbaum deiner Pipeline; jede Änderung erzeugt eine neue Version, zu der du jederzeit zurückspringen kannst\n\n' +
    '💡 Jede Anfrage führt genau **einen Schritt** aus. Ich schlage danach automatisch vor, was als nächstes sinnvoll ist.\n\n' +
    '**Nützliche Befehle:**\n\n' +
    '- `/help` — vollständige Dokumentation aller Schritte und Parameter (auch `/help preprocessing`, `/help modellierung`, ...)\n' +
    '- `/overview` — Datensatz-Profil (Spalten, Typen, fehlende Werte)\n' +
    '- `/status` — aktueller Stand der Pipeline und letzter Run\n\n' +
    '**Womit möchtest du starten?** Zum Beispiel:\n\n' +
    '- *„Zeig mir eine Übersicht der Daten"* — ich profiliere den Datensatz ohne ihn zu verändern\n' +
    '- *„Entferne doppelte Zeilen aus dem Datensatz"* — führt genau diesen einen Schritt aus\n' +
    '- *„Welche Spalten gibt es und was bedeuten sie?"* — ich erkläre den Datensatz\n\n' +
    'Klicke unten auf einen der Vorschläge oder schreib einfach los.',
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
    versionMetrics: {},
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

      // Metriken pro Spec-Version akkumulieren
      const versionMetrics = (() => {
        if (response.type !== 'result' || !response.metrics) return state.versionMetrics
        const ver = response.spec_summary?.spec_version_id
        if (!ver) return state.versionMetrics
        return { ...state.versionMetrics, [ver]: response.metrics }
      })()

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
        versionMetrics,
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
        // Metriken per spec_version aus dem ersten Artefakt ableiten
        const pollSpecVersion = action.artifacts?.[0]?.spec_version
        const versionMetrics =
          action.metrics && pollSpecVersion
            ? { ...state.versionMetrics, [pollSpecVersion]: action.metrics }
            : state.versionMetrics
        return {
          ...state,
          ui: { type: 'run_done' },
          lastRun,
          versionMetrics,
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
