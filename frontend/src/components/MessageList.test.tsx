import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ChatMessage } from '../types'
import { MessageList } from './MessageList'

const proposalMessage: ChatMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Vorschlag-Fallback-Text',
  ts: new Date().toISOString(),
  response: {
    type: 'proposal',
    proposal_id: 'prop-001',
    message: 'Vorschlag',
    steps: [{ step_type: 'load_csv', parameters_summary: '' }],
  },
}

const userMessage: ChatMessage = {
  id: 'msg-2',
  role: 'user',
  content: 'Hallo',
  ts: new Date().toISOString(),
}

describe('MessageList — Proposal isActive-Ableitung', () => {
  it('zeigt Proposal als aktiv wenn proposal_id mit activePendingProposalId übereinstimmt', () => {
    render(
      <MessageList
        messages={[proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId="prop-001"
      />,
    )
    expect(screen.getByRole('button', { name: /bestätigen/i })).toBeInTheDocument()
    expect(screen.getByText('Vorschlag (noch nicht ausgeführt)')).toBeInTheDocument()
  })

  it('zeigt Proposal als überschrieben wenn activePendingProposalId null ist', () => {
    render(
      <MessageList
        messages={[proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId={null}
      />,
    )
    expect(screen.queryByRole('button', { name: /bestätigen/i })).not.toBeInTheDocument()
    expect(screen.getByText('Vorschlag (nicht bestätigt)')).toBeInTheDocument()
  })

  it('zeigt Proposal als überschrieben wenn activePendingProposalId eine andere ID ist', () => {
    render(
      <MessageList
        messages={[proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId="prop-002"
      />,
    )
    expect(screen.queryByRole('button', { name: /bestätigen/i })).not.toBeInTheDocument()
    expect(screen.getByText('Vorschlag (nicht bestätigt)')).toBeInTheDocument()
  })
})

describe('MessageList — Grundlegendes Rendering', () => {
  it('rendert User-Nachrichten', () => {
    render(
      <MessageList
        messages={[userMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId={null}
      />,
    )
    expect(screen.getByText('Hallo')).toBeInTheDocument()
  })

  it('rendert leere Liste ohne Fehler', () => {
    render(
      <MessageList
        messages={[]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId={null}
      />,
    )
    expect(screen.queryAllByTestId('chat-message')).toHaveLength(0)
  })

  it('rendert mehrere Nachrichten', () => {
    render(
      <MessageList
        messages={[userMessage, proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId="prop-001"
      />,
    )
    expect(screen.getAllByTestId('chat-message')).toHaveLength(2)
  })
})

describe('MessageList — ResultCard Integration', () => {
  const resultMessage: ChatMessage = {
    id: 'msg-result',
    role: 'assistant',
    content: 'Fallback-Text',
    ts: new Date().toISOString(),
    response: {
      type: 'result',
      message: 'Run abgeschlossen.',
      status: 'done',
      metrics: { rmse: 123.45 },
    },
  }

  it('rendert Result-Message als ResultCard, nicht als Plain-Text', () => {
    const { container } = render(
      <MessageList
        messages={[resultMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId={null}
      />,
    )
    expect(screen.getByText('Ergebnis')).toBeInTheDocument()
    expect(screen.getByText('Run abgeschlossen.')).toBeInTheDocument()
    expect(container.querySelector('.resultCard')).toBeInTheDocument()
    // Fallback-Text sollte NICHT als messageContent gerendert werden
    expect(container.querySelector('.messageContent')).not.toBeInTheDocument()
  })

  it('rendert Proposal-Messages weiterhin als ProposalCard (Regression)', () => {
    const { container } = render(
      <MessageList
        messages={[proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId="prop-001"
      />,
    )
    expect(container.querySelector('.proposalCard')).toBeInTheDocument()
    expect(container.querySelector('.resultCard')).not.toBeInTheDocument()
  })
})
