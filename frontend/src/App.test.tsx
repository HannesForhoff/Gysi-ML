import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { AssistantResponse } from './types'

function mockFrontendEnv() {
  vi.doMock('./env', () => ({
    getFrontendEnv: () => ({
      backendBaseUrl: 'http://localhost:8000',
      useMock: true,
    }),
  }))
}

function createDefaultAssistantResponse(userText: string): AssistantResponse {
  const text = userText.trim().toLowerCase()

  if (
    text.includes('undo') ||
    text.includes('rückgängig') ||
    text.includes('revert') ||
    text.includes('rollback') ||
    text.includes('berichtigen') ||
    text.includes('korrigieren')
  ) {
    return {
      type: 'info',
      message:
        'Zu früheren Versionen kannst du nur manuell über den Versionsbaum im Tree zurückgehen. Der Chat kann keinen Rollback auslösen und bereits durchgeführte Schritte nicht nachträglich berichtigen.',
    }
  }

  if (text.includes('proposal') || text.includes('vorschlag')) {
    return {
      type: 'proposal',
      proposal_id: 'mock-proposal-001',
      message: 'Vorschlag (Mock): Ich würde die Pipeline wie folgt anpassen.',
      steps: [
        { step_type: 'load_csv', parameters_summary: 'source=data/raw/bike.csv' },
        { step_type: 'impute_missing', parameters_summary: 'strategy=median' },
        { step_type: 'train_test_split', parameters_summary: 'test_size=0.2, random_state=42' },
      ],
    }
  }

  if (text.includes('error') || text.includes('fehler') || text.includes('fail')) {
    return {
      type: 'error',
      message: 'Validierungsfehler (Mock): Step `unknown_step` existiert nicht.',
      details: 'Validierungsfehler aufgetreten',
    }
  }

  return {
    type: 'result',
    message: 'Ergebnis (Mock): Run abgeschlossen.',
    status: 'done',
  }
}

function mockDefaultTransport() {
  vi.doMock('./api/transport', () => ({
    sendAssistantMessage: vi.fn().mockImplementation(async ({ userText, sessionId }) => ({
      sessionId: sessionId ?? 'mock',
      response: createDefaultAssistantResponse(userText),
    })),
    confirmProposal: vi.fn().mockResolvedValue({ runId: 'mock-run-001' }),
  }))
}

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
    vi.resetModules()
    mockFrontendEnv()
    mockDefaultTransport()
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')

    await user.type(textarea, 'Hallo{shift>}{enter}{/shift}Welt')
    expect(textarea).toHaveValue('Hallo\nWelt')

    expect(screen.queryAllByTestId('chat-message')).toHaveLength(1) // welcome message

    await user.type(textarea, '{enter}')

    expect(textarea).toHaveValue('')
    expect(textarea).toHaveFocus()

    await screen.findByText(/Ergebnis \(Mock\): Run abgeschlossen\./)
  })

  it('Mock send/receive: User- und Assistant-Message erscheinen', async () => {
    vi.resetModules()
    mockFrontendEnv()
    mockDefaultTransport()
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
    vi.resetModules()
    mockFrontendEnv()
    mockDefaultTransport()
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
    mockFrontendEnv()

    const d = deferred<{ sessionId: string | null; response: AssistantResponse }>()
    const sendAssistantMessageMock = vi.fn(() => d.promise)

    vi.doMock('./api/transport', () => ({
      sendAssistantMessage: sendAssistantMessageMock,
      confirmProposal: vi.fn().mockResolvedValue({ runId: 'mock-run-001' }),
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

  it('Undo-Mock \u2014 zeigt Hinweis auf manuellen Tree-Rollback statt Spec-Änderung', async () => {
    vi.resetModules()
    mockFrontendEnv()
    vi.doMock('./api/transport', () => ({
      sendAssistantMessage: vi.fn().mockResolvedValue({
        sessionId: 'mock',
        response: {
          type: 'info',
          message:
            'Zu früheren Versionen kannst du nur manuell über den Versionsbaum im Tree zurückgehen. Der Chat kann keinen Rollback auslösen und bereits durchgeführte Schritte nicht nachträglich berichtigen.',
        },
      }),
      confirmProposal: vi.fn(),
    }))
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')

    await user.type(textarea, 'undo{enter}')

    await screen.findByText(/nur manuell über den Versionsbaum im Tree zurückgehen/i)
    expect(screen.queryByText(/mock-spec-undo-v1/)).not.toBeInTheDocument()
  })

  it('Proposal Mock — Card sichtbar statt plain Text', async () => {
    vi.resetModules()
    mockFrontendEnv()
    mockDefaultTransport()
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
    mockFrontendEnv()
    mockDefaultTransport()
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    await user.type(textarea, 'vorschlag{enter}')

    await screen.findByText(/Vorschlag \(noch nicht ausgeführt\)/)

    expect(screen.getByText('load_csv')).toBeInTheDocument()
    expect(screen.getByText('Fehlende Werte auffüllen')).toBeInTheDocument()
    expect(screen.getByText('train_test_split')).toBeInTheDocument()
  })

  it('Proposal Mock — Confirm-Button vorhanden', async () => {
    vi.resetModules()
    mockFrontendEnv()
    mockDefaultTransport()
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
    mockFrontendEnv()
    mockDefaultTransport()
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
    mockFrontendEnv()
    mockDefaultTransport()
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

  it('Bug 1.13: Draft-Text überlebt Tab-Wechsel zu "Artefakte & Steps" und zurück', async () => {
    vi.resetModules()
    mockFrontendEnv()
    mockDefaultTransport()
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    const textarea = screen.getByLabelText('Composer')
    await user.type(textarea, 'Hallo Welt')
    expect(textarea).toHaveValue('Hallo Welt')

    await user.click(screen.getByRole('button', { name: 'Artefakte & Steps' }))
    await user.click(screen.getByRole('button', { name: 'Chat' }))

    expect(screen.getByLabelText('Composer')).toHaveValue('Hallo Welt')
  })

  it('Bug 1.13: Draft-Text überlebt Tab-Wechsel zu "Daten" und zurück', async () => {
    // IntersectionObserver wird von DataViewPanel (infinite scroll) benötigt, ist aber in jsdom nicht implementiert
    const observerMock = vi.fn(() => ({ observe: vi.fn(), unobserve: vi.fn(), disconnect: vi.fn() }))
    vi.stubGlobal('IntersectionObserver', observerMock)

    vi.resetModules()
    mockFrontendEnv()
    vi.doMock('./api/transport', () => ({
      sendAssistantMessage: vi.fn().mockResolvedValue({
        sessionId: 'mock-session',
        response: { type: 'result', message: 'Antwort vom Mock', status: 'done' },
      }),
      confirmProposal: vi.fn().mockResolvedValue({ runId: 'mock-run-001' }),
    }))
    const { default: App } = await import('./App')

    const user = userEvent.setup()
    render(<App />)

    // Erste Nachricht senden, damit die Session gesetzt wird und der Daten-Tab aktiv wird
    const textarea = screen.getByLabelText('Composer')
    await user.type(textarea, 'hallo{enter}')
    await screen.findByText('Antwort vom Mock')

    // Draft eintippen, ohne abzusenden
    await user.type(textarea, 'Draft bleibt erhalten')
    expect(textarea).toHaveValue('Draft bleibt erhalten')

    // Zum Daten-Tab wechseln und zurück
    await user.click(screen.getByRole('button', { name: 'Daten' }))
    await user.click(screen.getByRole('button', { name: 'Chat' }))

    expect(screen.getByLabelText('Composer')).toHaveValue('Draft bleibt erhalten')
  })
})
