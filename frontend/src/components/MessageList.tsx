import React from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { ChatMessage } from '../types'
import { ProposalCard } from './ProposalCard'
import { ResultCard } from './ResultCard'

type CorrPairAll = {
  col_a: string
  col_b: string
  value: number
  above_threshold: boolean
  suggestion: string | null
}

type FeatureImportanceEntry = {
  name: string
  importance: number
  selected: boolean
}

function buildFeatureImportanceTableMarkdown(
  importances: FeatureImportanceEntry[],
  topN: number,
): string {
  const rows = importances.map((f, i) => {
    const rank = i + 1
    const status = f.selected ? '✓ behalten' : '⚠ Vorschlag: entfernen'
    return `| ${rank} | \`${f.name}\` | ${f.importance.toFixed(2)} % | ${status} |`
  })
  return [
    `**CatBoost Feature-Importance** (Top-${topN} Vorschlag — noch nichts entfernt)`,
    '',
    '| # | Feature | Importance | Vorschlag |',
    '|---|---------|------------|-----------|',
    ...rows,
  ].join('\n')
}

function buildCorrTableMarkdown(pairs: CorrPairAll[], threshold: number): string {
  const rows = pairs.map((p) => {
    const val = p.value.toFixed(4)
    const suggestion = p.above_threshold && p.suggestion ? `${p.suggestion} entfernen?` : '—'
    return `| \`${p.col_a}\` | \`${p.col_b}\` | ${val} | ${suggestion} |`
  })
  return [
    `**Korrelationsanalyse** (Schwellwert: |r| ≥ ${threshold})`,
    '',
    '| Spalte A | Spalte B | r-Wert | Vorschlag |',
    '|----------|----------|--------|-----------|',
    ...rows,
  ].join('\n')
}

type MessageListProps = {
  messages: ChatMessage[]
  onConfirm: (proposalId: string) => void
  confirmDisabled: boolean
  activePendingProposalId: string | null
  isSending?: boolean
}

const mdComponents = {
  table: ({ children, ...props }: React.HTMLAttributes<HTMLTableElement>) => (
    <div className="mdTableWrapper">
      <table {...props}>{children}</table>
    </div>
  ),
}

function GysiAvatar() {
  return <img src="/icon.png" alt="Gysi" className="avatarImg" aria-hidden="true" />
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
              {message.role === 'assistant' ? (
                <GysiAvatar />
              ) : (
                <div className="avatar" aria-hidden="true">
                  {message.role === 'user' ? 'U' : 'S'}
                </div>
              )}
              <div className="bubble">
                <div className="bubbleMeta">
                  <span className="messageRole">
                    {message.role === 'assistant' ? 'Gysi' : message.role === 'user' ? 'Du' : 'System'}
                  </span>
                  <span className="messageTs">
                    {new Date(message.ts).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                  </span>
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
                    <Markdown remarkPlugins={[remarkGfm]} components={mdComponents}>{message.content}</Markdown>
                  </div>
                ) : (
                  <div className="messageContent">{message.content}</div>
                )}
              </div>
            </div>
          </li>
          {(() => {
            if (message.response?.type !== 'result') return null
            const catboostStep = message.response.step_results?.find(
              (sr) =>
                sr.step_type === 'catboost_feature_selection' &&
                sr.metadata?.analysis_only === true,
            )
            const importances = catboostStep?.metadata?.feature_importances as
              | FeatureImportanceEntry[]
              | undefined
            if (!importances || importances.length === 0) return null
            const topN = importances.filter((f) => f.selected).length
            return (
              <li className="message" data-role="assistant" data-testid="feature-importance-table">
                <div className="messageRow">
                  <GysiAvatar />
                  <div className="bubble">
                    <div className="bubbleMeta">
                      <span className="messageRole">Gysi</span>
                      <span className="messageTs">
                        {new Date(message.ts).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="messageContent">
                      <Markdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                        {buildFeatureImportanceTableMarkdown(importances, topN)}
                      </Markdown>
                    </div>
                  </div>
                </div>
              </li>
            )
          })()}
          {(() => {
            if (message.response?.type !== 'result') return null
            const corrStep = message.response.step_results?.find(
              (sr) => sr.step_type === 'correlation_filter' && sr.metadata?.analysis_only === true,
            )
            const allPairs = corrStep?.metadata?.all_corr_pairs as CorrPairAll[] | undefined
            if (!allPairs || allPairs.length === 0) return null
            const threshold = (corrStep?.metadata?.threshold as number | undefined) ?? 0.9
            return (
              <li className="message" data-role="assistant" data-testid="correlation-table">
                <div className="messageRow">
                  <GysiAvatar />
                  <div className="bubble">
                    <div className="bubbleMeta">
                      <span className="messageRole">Gysi</span>
                      <span className="messageTs">
                        {new Date(message.ts).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="messageContent">
                      <Markdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                        {buildCorrTableMarkdown(allPairs, threshold)}
                      </Markdown>
                    </div>
                  </div>
                </div>
              </li>
            )
          })()}
          {message.response?.type === 'result' && message.response.post_run_explanation && (
            <li
              className="message"
              data-role="assistant"
              data-testid="post-run-explanation"
            >
              <div className="messageRow">
                <GysiAvatar />
                <div className="bubble">
                  <div className="bubbleMeta">
                    <span className="messageRole">Gysi</span>
                    <span className="messageTs">
                      {new Date(message.ts).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="messageContent">
                    <Markdown remarkPlugins={[remarkGfm]} components={mdComponents}>{message.response.post_run_explanation}</Markdown>
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
            <GysiAvatar />
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
