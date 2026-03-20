import type { ChatMessage } from '../types'
import { ProposalCard } from './ProposalCard'
import { ResultCard } from './ResultCard'

type MessageListProps = {
  messages: ChatMessage[]
  onConfirm: (proposalId: string) => void
  confirmDisabled: boolean
  activePendingProposalId: string | null
}

export function MessageList({ messages, onConfirm, confirmDisabled, activePendingProposalId }: MessageListProps) {
  return (
    <ol className="messageList" aria-label="Chat messages">
      {messages.map((message) => (
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
              ) : (
                <div className="messageContent">{message.content}</div>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
