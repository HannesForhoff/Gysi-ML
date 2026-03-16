import './App.css'

import { useCallback, useReducer } from 'react'

import { sendAssistantMessage } from './api/transport'
import { ChatLayout } from './components/ChatLayout'
import { Composer } from './components/Composer'
import { MessageList } from './components/MessageList'
import { StatusPanel } from './components/StatusPanel'
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
  }
}

function App() {
  const [state, dispatch] = useReducer(chatReducer, undefined, createInitialChatState)
  const isSending = state.ui.type === 'sending_message'

  const handleSend = useCallback(
    async (text: string) => {
      if (state.ui.type === 'sending_message') return

      const userMessage = createMessage('user', text)
      dispatch({ type: 'SEND_REQUEST_STARTED', userMessage })

      try {
        const response = await sendAssistantMessage(text)
        const assistantMessage = createMessage(
          'assistant',
          formatAssistantResponse(response),
        )

        dispatch({
          type: 'SEND_REQUEST_SUCCEEDED',
          assistantMessage,
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
    [state.ui.type],
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
          <MessageList messages={state.messages} />
          <Composer disabled={isSending} onSend={handleSend} />
        </ChatLayout>
      </div>
    </div>
  )
}

export default App
