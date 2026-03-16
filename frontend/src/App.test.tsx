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
    expect(screen.getByText(/UI State: validation_error/)).toBeInTheDocument()

    await user.type(textarea, 'proposal')
    expect(sendButton).not.toBeDisabled()

    await user.type(textarea, '{enter}')

    await screen.findByText(/Vorschlag \(Mock\):/)
    expect(screen.getByText(/UI State: proposal_pending/)).toBeInTheDocument()
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
    expect(screen.getByText(/UI State: sending_message/)).toBeInTheDocument()
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
})
