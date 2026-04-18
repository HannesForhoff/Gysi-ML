import React from 'react'
import Markdown from 'react-markdown'

import type { ChatMessage } from '../types'
import { ProposalCard } from './ProposalCard'
import { ResultCard } from './ResultCard'

type MessageListProps = {
  messages: ChatMessage[]
  onConfirm: (proposalId: string) => void
  confirmDisabled: boolean
  activePendingProposalId: string | null
  isSending?: boolean
}

export function MessageList({ messages, onConfirm, confirmDisabled, activePendingProposalId, isSending }: MessageListProps) {
  return (
    <ol className="messageList" aria-label="Chat messages">
      {messages.map((message) => (
        <React.Fragment key={message.id}>
          <li
            key={message.id}
            className="message"
            data-role={message.role}
            data-testid="chat-message"
          >
            <div className="messageRow">
              <div className="avatar" aria-hidden="true">
                {message.role === 'assistant'
                  ? 'G'
                  : message.role === 'user'
                    ? 'U'
                    : 'S'}
              </div>
              <div className="bubble">
                <div className="bubbleMeta">
                  <span className="messageRole">{message.role}</span>
                  <span className="messageTs">{message.ts}</span>
                </div>
                {message.response?.type === 'proposal' ? (
                  <ProposalCard
                    proposal={message.response}
                    onConfirm={onConfirm}
                    disabled={confirmDisabled}
                    isActive={
                      activePendingProposalId !== null &&
                      message.response.proposal_id === activePendingProposalId
                    }
                  />
                ) : message.response?.type === 'result' ? (
                  <ResultCard result={message.response} />
                ) : message.role === 'assistant' ? (
                  <div className="messageContent">
                    <Markdown>{message.content}</Markdown>
                  </div>
                ) : (
                  <div className="messageContent">{message.content}</div>
                )}
              </div>
            </div>
          </li>
          {message.response?.type === 'result' && message.response.post_run_explanation && (
            <li
              className="message"
              data-role="assistant"
              data-testid="post-run-explanation"
            >
              <div className="messageRow">
                <div className="avatar" aria-hidden="true">G</div>
                <div className="bubble">
                  <div className="bubbleMeta">
                    <span className="messageRole">assistant</span>
                    <span className="messageTs">{message.ts}</span>
                  </div>
                  <div className="messageContent">
                    <Markdown>{message.response.post_run_explanation}</Markdown>
                  </div>
                </div>
              </div>
            </li>
          )}
        </React.Fragment>
      ))}
      {isSending && (
        <li className="message" data-role="assistant" data-testid="typing-indicator">
          <div className="messageRow">
            <div className="avatar" aria-hidden="true">G</div>
            <div className="bubble">
              <div className="typingIndicator" aria-label="Gysi rechnet...">
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
        </li>
      )}
    </ol>
  )
}
