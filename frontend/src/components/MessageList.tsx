import type { ChatMessage } from '../types'

type MessageListProps = {
  messages: ChatMessage[]
}

export function MessageList({ messages }: MessageListProps) {
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
              <div className="messageContent">{message.content}</div>
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
