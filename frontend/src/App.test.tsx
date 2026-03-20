import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { AssistantResponse } from './types'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void

  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })

  return { promise, resolve, reject }
}

describe('gysi-ml frontend (Story 1.1 smoke tests)', () => {
  it('Composer: Shift+Enter inserts newline, Enter sends and keeps focus', async () => {
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')

    await user.type(textarea, 'Hallo{shift>}{enter}{/shift}Welt')
    expect(textarea).toHaveValue('Hallo\nWelt')

    expect(screen.queryAllByTestId('chat-message')).toHaveLength(0)

    await user.type(textarea, '{enter}')

    expect(textarea).toHaveValue('')
    expect(textarea).toHaveFocus()

    await screen.findByText(/Ergebnis \(Mock\): Run abgeschlossen\./)
  })

  it('Mock send/receive: User- und Assistant-Message erscheinen', async () => {
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')

    await user.type(textarea, 'proposal{enter}')

    await screen.findByText(/Vorschlag \(Mock\):/)

    const messages = screen.getAllByTestId('chat-message')
    expect(messages.length).toBeGreaterThanOrEqual(2)
  })

  it('Validation error: nach Fehler sofort wieder senden moeglich', async () => {
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    const sendButton = screen.getByLabelText('Send')

    await user.type(textarea, 'error{enter}')

    await screen.findByText(/Validierungsfehler \(Mock\):/)
    expect(screen.getByText(/Validierungsfehler aufgetreten/)).toBeInTheDocument()

    await user.type(textarea, 'proposal')
    expect(sendButton).not.toBeDisabled()

    await user.type(textarea, '{enter}')

    await screen.findByText(/Vorschlag \(Mock\):/)
    expect(screen.getByText(/Vorschlag ausstehend/)).toBeInTheDocument()
  })

  it('Kein Doppelsenden: Send ist disabled während Request läuft', async () => {
    vi.resetModules()

    const d = deferred<{ sessionId: string | null; response: AssistantResponse }>()
    const sendAssistantMessageMock = vi.fn(() => d.promise)

    vi.doMock('./api/transport', () => ({
      sendAssistantMessage: sendAssistantMessageMock,
    }))

    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    const sendButton = screen.getByLabelText('Send')

    await user.type(textarea, 'hi{enter}')

    expect(sendAssistantMessageMock).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/Sendet…/)).toBeInTheDocument()
    expect(sendButton).toBeDisabled()

    await user.type(textarea, 'again{enter}')
    expect(sendAssistantMessageMock).toHaveBeenCalledTimes(1)

    const userMessages = screen
      .getAllByTestId('chat-message')
      .filter((el) => el.getAttribute('data-role') === 'user')

    expect(userMessages).toHaveLength(1)

    d.resolve({
      sessionId: 'mock',
      response: { type: 'result', message: 'ok', status: 'done' },
    })

    await screen.findByText(/ok/)
  })

  it('spec_updated Mock \u2014 Spec Summary im Status-Panel aktualisiert sich', async () => {
    vi.resetModules()
    vi.doUnmock('./api/transport')
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')

    await user.type(textarea, 'undo{enter}')

    await screen.findByText(/Spec aktualisiert \(Mock\)/)

    expect(screen.getByText(/mock-spec-undo-v1/)).toBeInTheDocument()
  })

  it('Proposal Mock — Card sichtbar statt plain Text', async () => {
    vi.resetModules()
    vi.doUnmock('./api/transport')
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    await user.type(textarea, 'vorschlag{enter}')

    await screen.findByText(/Vorschlag \(noch nicht ausgeführt\)/)

    // plain-Text-Format darf nicht vorkommen (StepsBlock aus formatAssistantResponse)
    expect(screen.queryByText(/^Steps:$/m)).not.toBeInTheDocument()
  })

  it('Proposal Mock — Steps aus Fixture gelistet', async () => {
    vi.resetModules()
    vi.doUnmock('./api/transport')
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    await user.type(textarea, 'vorschlag{enter}')

    await screen.findByText(/Vorschlag \(noch nicht ausgeführt\)/)

    expect(screen.getByText('load_csv')).toBeInTheDocument()
    expect(screen.getByText('impute_missing')).toBeInTheDocument()
    expect(screen.getByText('train_test_split')).toBeInTheDocument()
  })

  it('Proposal Mock — Confirm-Button vorhanden', async () => {
    vi.resetModules()
    vi.doUnmock('./api/transport')
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    await user.type(textarea, 'proposal{enter}')

    await screen.findByText(/Vorschlag \(noch nicht ausgeführt\)/)

    expect(
      screen.getByRole('button', { name: /Bestätigen/i }),
    ).toBeInTheDocument()
  })

  it('Nicht-Proposal bleibt plain Text (keine Regression)', async () => {
    vi.resetModules()
    vi.doUnmock('./api/transport')
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    await user.type(textarea, 'error{enter}')

    await screen.findByText(/Validierungsfehler \(Mock\):/)

    // Keine ProposalCard im DOM
    expect(document.querySelector('.proposalCard')).toBeNull()
  })

  it('Confirm-Flow Mock: Klick auf Bestätigen wechselt State auf run_polling', async () => {
    vi.resetModules()
    vi.doUnmock('./api/transport')
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')

    // Proposal auslösen
    await user.type(textarea, 'proposal{enter}')
    await screen.findByText(/Vorschlag \(noch nicht ausgeführt\)/)

    // Button ist klickbar im proposal_pending-State
    const confirmButton = screen.getByRole('button', { name: /Bestätigen/i })
    expect(confirmButton).not.toBeDisabled()

    // Confirm auslösen
    await user.click(confirmButton)

    // Nach Mock-Confirm wechselt UI auf run_polling
    await screen.findByText(/Run läuft…/)
  })
})
