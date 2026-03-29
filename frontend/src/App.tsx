import './App.css'

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import { fetchSpecSummary, fetchSpecTree, performRollback } from './api/healthApi'
import { confirmProposal, sendAssistantMessage } from './api/transport'
import { ChatLayout } from './components/ChatLayout'
import { Composer } from './components/Composer'
import { MessageList } from './components/MessageList'
import { SpecHistoryPanel } from './components/SpecHistoryPanel'
import { StatusPanel } from './components/StatusPanel'
import { useHealthPolling } from './hooks/useHealthPolling'
import { useRunPolling } from './hooks/useRunPolling'
import { chatReducer, createInitialChatState } from './state/chatReducer'
import type { AssistantResponse, ChatMessage } from './types'

function createId(): string {
  const cryptoObj = globalThis.crypto
  if (cryptoObj && 'randomUUID' in cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    return cryptoObj.randomUUID()
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createMessage(role: ChatMessage['role'], content: string): ChatMessage {
  return {
    id: createId(),
    role,
    content,
    ts: new Date().toISOString(),
  }
}

function formatAssistantResponse(response: AssistantResponse): string {
  switch (response.type) {
    case 'proposal': {
      const steps = response.steps
        .map((s) => `- ${s.step_type}${s.parameters_summary ? ` (${s.parameters_summary})` : ''}`)
        .join('\n')

      return `${response.message}\n\nSteps:\n${steps}`
    }

    case 'result': {
      const metrics = response.metrics
        ? `\n\nMetrics:\n${Object.entries(response.metrics)
            .map(([k, v]) => `- ${k}: ${String(v)}`)
            .join('\n')}`
        : ''

      const artifacts = response.artifacts
        ? `\n\nArtifacts:\n${response.artifacts.map((a) => `- ${a.label} (${a.media_type})`).join('\n')}`
        : ''

      return `${response.message}\n\nStatus: ${response.status}${metrics}${artifacts}`
    }

    case 'error':
      return response.details ? `${response.message}\n\n${response.details}` : response.message

    case 'spec_updated':
      return response.message

    case 'info':
      return response.message
  }
}

function App() {
  const [state, dispatch] = useReducer(chatReducer, undefined, createInitialChatState)
  const isSending = state.ui.type === 'sending_message'

  const [isRollingBack, setIsRollingBack] = useState(false)
  const [rollbackTargetId, setRollbackTargetId] = useState<string | null>(null)

  // Prevent double-fetch of specTree when session changes
  const specTreeSessionRef = useRef<string | null>(null)

  useHealthPolling(dispatch, state.transport)
  useRunPolling(dispatch, state)

  useEffect(() => {
    if (state.transport.useMock) return
    if (!state.sessionId || state.specSummary !== null) return

    let cancelled = false
    void fetchSpecSummary(state.transport.backendBaseUrl, state.sessionId).then(
      (result) => {
        if (!cancelled && result !== null) {
          dispatch({ type: 'SPEC_SUMMARY_LOADED', specSummary: result })
        }
      },
    )
    return () => {
      cancelled = true
    }
  }, [state.sessionId, state.specSummary, state.transport.useMock, state.transport.backendBaseUrl])

  // Lade den Spec-Tree initial und wenn sich die Session ändert
  useEffect(() => {
    if (state.transport.useMock) return
    if (!state.sessionId) return
    if (specTreeSessionRef.current === state.sessionId) return

    specTreeSessionRef.current = state.sessionId
    let cancelled = false
    void fetchSpecTree(state.transport.backendBaseUrl, state.sessionId).then((result) => {
      if (!cancelled && result !== null) {
        dispatch({ type: 'SPEC_TREE_LOADED', specTree: result })
      }
    })
    return () => {
      cancelled = true
    }
  }, [state.sessionId, state.transport.useMock, state.transport.backendBaseUrl])
  const handleSend = useCallback(
    async (text: string) => {
      if (state.ui.type === 'sending_message') return

      const userMessage = createMessage('user', text)
      dispatch({ type: 'SEND_REQUEST_STARTED', userMessage })

      try {
        const { sessionId, response } = await sendAssistantMessage({
          userText: text,
          sessionId: state.sessionId,
        })
        const assistantMessage: ChatMessage = {
          ...createMessage('assistant', formatAssistantResponse(response)),
          response,
        }

        dispatch({
          type: 'SEND_REQUEST_SUCCEEDED',
          assistantMessage,
          sessionId,
          response,
        })
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error'
        const assistantMessage = createMessage('assistant', errorMessage)

        dispatch({
          type: 'SEND_REQUEST_FAILED',
          assistantMessage,
          errorMessage,
        })
      }
    },
    [state.sessionId, state.ui.type],
  )

  const handleConfirm = useCallback(
    async (proposalId: string) => {
      if (state.isConfirming || state.ui.type !== 'proposal_pending') return

      if (!state.sessionId) {
        dispatch({ type: 'CONFIRM_FAILED', errorMessage: 'Keine Session-ID vorhanden.' })
        return
      }

      dispatch({ type: 'CONFIRM_STARTED' })

      try {
        const result = await confirmProposal({
          proposalId,
          sessionId: state.sessionId,
        })

        if (result.error || !result.runId) {
          dispatch({
            type: 'CONFIRM_FAILED',
            errorMessage: result.error ?? 'Confirm fehlgeschlagen.',
          })
          return
        }

        dispatch({ type: 'CONFIRM_SUCCEEDED', runId: result.runId })
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unbekannter Fehler'
        dispatch({ type: 'CONFIRM_FAILED', errorMessage })
      }
    },
    [state.isConfirming, state.ui.type, state.sessionId],
  )

  const handleRollback = useCallback(
    async (targetSpecId: string) => {
      if (!state.sessionId || isRollingBack) return

      setIsRollingBack(true)
      setRollbackTargetId(targetSpecId)

      const result = await performRollback(
        state.transport.backendBaseUrl,
        state.sessionId,
        targetSpecId,
      )

      if (result.ok) {
        const [newSummary, newTree] = await Promise.all([
          fetchSpecSummary(state.transport.backendBaseUrl, state.sessionId),
          fetchSpecTree(state.transport.backendBaseUrl, state.sessionId),
        ])
        dispatch({
          type: 'ROLLBACK_SUCCEEDED',
          infoMessage: createMessage(
            'assistant',
            `Rollback zu **${result.newVersion}** abgeschlossen. Die Pipeline wurde auf diesen Stand zurückgesetzt.`,
          ),
          specTree: newTree ?? state.specHistory!,
          specSummary: newSummary,
        })
      } else {
        dispatch({
          type: 'ROLLBACK_FAILED',
          errorMessage: result.error,
          errorChatMessage: createMessage('assistant', `Rollback fehlgeschlagen: ${result.error}`),
        })
      }

      setIsRollingBack(false)
      setRollbackTargetId(null)
    },
    [
      state.sessionId,
      state.transport.backendBaseUrl,
      state.specHistory,
      isRollingBack,
    ],
  )

  // Spec-Tree nach jeder Aktion neu laden (execute/confirm)
  const prevUiType = useRef(state.ui.type)
  useEffect(() => {
    const prev = prevUiType.current
    prevUiType.current = state.ui.type

    const justFinished =
      (prev === 'sending_message' || prev === 'run_polling') &&
      (state.ui.type === 'run_done' || state.ui.type === 'idle' || state.ui.type === 'run_failed')

    if (!justFinished || !state.sessionId || state.transport.useMock) return

    void fetchSpecTree(state.transport.backendBaseUrl, state.sessionId).then((result) => {
      if (result !== null) {
        dispatch({ type: 'SPEC_TREE_LOADED', specTree: result })
      }
    })
  }, [state.ui.type, state.sessionId, state.transport.backendBaseUrl, state.transport.useMock])

  return (
    <div className="page">
      <div className="shell">
        <header className="shellHeader">
          <div className="brandGroup">
            <div className="brandLogo">
              <img src="/icon.png" alt="Gysi Logo" className="brandLogoImg" />
              <span className="brandTitle">Gysi</span>
            </div>
            <span className="brandSubtitle">Live-Demo</span>
            <span className="brandBadge">
              {state.transport.useMock
                ? 'Mock-Modus'
                : state.llmModel ?? '…'}
            </span>
          </div>
          <div className={`headerStatus ${state.ui.type === 'backend_unreachable' ? 'headerStatus--disconnected' : ''}`}>
            <span className="headerStatusDot" />
            <span className="headerStatusText">
              {state.ui.type === 'backend_unreachable' ? 'Getrennt' : 'Verbunden'}
            </span>
          </div>
        </header>

        <ChatLayout
          status={
            <StatusPanel
              transport={state.transport}
              ui={state.ui}
              specSummary={state.specSummary}
              lastRun={state.lastRun}
              artifacts={state.artifacts}
              lastError={state.lastError}
              isLongRunning={state.isLongRunning}
            />
          }
          history={
            <SpecHistoryPanel
              sessionId={state.sessionId}
              specHistory={state.specHistory}
              onRollback={handleRollback}
              isRollingBack={isRollingBack}
              rollbackTargetId={rollbackTargetId}
            />
          }
        >
          <MessageList
            messages={state.messages}
            onConfirm={handleConfirm}
            confirmDisabled={state.isConfirming || state.ui.type !== 'proposal_pending'}
            activePendingProposalId={state.pendingProposalId}
            isSending={isSending}
          />
          <Composer disabled={isSending} onSend={handleSend} />
        </ChatLayout>
      </div>
    </div>
  )
}

export default App
