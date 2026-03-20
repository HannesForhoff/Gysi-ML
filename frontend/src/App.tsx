import './App.css'

import { useCallback, useEffect, useReducer } from 'react'

import { fetchSpecSummary } from './api/healthApi'
import { confirmProposal, sendAssistantMessage } from './api/transport'
import { ChatLayout } from './components/ChatLayout'
import { Composer } from './components/Composer'
import { MessageList } from './components/MessageList'
import { StatusPanel } from './components/StatusPanel'
import { useHealthPolling } from './hooks/useHealthPolling'
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
  }
}

function App() {
  const [state, dispatch] = useReducer(chatReducer, undefined, createInitialChatState)
  const isSending = state.ui.type === 'sending_message'

  useHealthPolling(dispatch, state.transport)

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

  return (
    <div className="page">
      <div className="shell">
        <header className="shellHeader">
          <div className="brand">
            <div className="brandTitle">gysi-ml</div>
            <div className="brandSubtitle">Mock-first Chat UI</div>
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
            />
          }
        >
          <MessageList
            messages={state.messages}
            onConfirm={handleConfirm}
            confirmDisabled={state.isConfirming || state.ui.type !== 'proposal_pending'}
          />
          <Composer disabled={isSending} onSend={handleSend} />
        </ChatLayout>
      </div>
    </div>
  )
}

export default App
