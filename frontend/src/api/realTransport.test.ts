import { afterEach, describe, expect, it, vi } from 'vitest'

import { sendRealMessage } from './realTransport'

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('realTransport', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('ohne sessionId: erstellt Session und sendet danach Message', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    fetchMock
      .mockResolvedValueOnce(jsonResponse({ session_id: 'session-123' }))
      .mockResolvedValueOnce(
        jsonResponse({ type: 'result', message: 'done', status: 'done' }),
      )

    const result = await sendRealMessage('http://localhost:8000/', {
      userText: 'hallo',
      sessionId: null,
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/v1/sessions',
      expect.objectContaining({ method: 'POST', body: '{}' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/v1/sessions/session-123/messages',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: 'hallo' }),
      }),
    )

    expect(result).toEqual({
      sessionId: 'session-123',
      response: { type: 'result', message: 'done', status: 'done' },
    })
  })

  it('mit sessionId: ruft sessions nicht erneut auf', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    fetchMock.mockResolvedValueOnce(
      jsonResponse({ type: 'proposal', message: 'ok', steps: [] }),
    )

    const result = await sendRealMessage('http://localhost:8000', {
      userText: 'next',
      sessionId: 'session-123',
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/v1/sessions/session-123/messages',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: 'next' }),
      }),
    )
    expect(result).toEqual({
      sessionId: 'session-123',
      response: { type: 'proposal', message: 'ok', steps: [] },
    })
  })

  it('network error: fetch throw wird weitergeworfen', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(
      sendRealMessage('http://localhost:8000', {
        userText: 'next',
        sessionId: 'session-123',
      }),
    ).rejects.toThrow('Failed to fetch')
  })

  it('HTTP 4xx/5xx mit JSON: liefert typed error und wirft nicht', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { error: 'validation failed', detail: 'invalid input', code: 'E400' },
        { status: 400 },
      ),
    )

    const result = await sendRealMessage('http://localhost:8000', {
      userText: 'oops',
      sessionId: 'session-123',
    })

    expect(result).toEqual({
      sessionId: 'session-123',
      response: {
        type: 'error',
        message: 'invalid input',
        details: 'E400',
      },
    })
  })

  it('Backend proposal: explanation → message, steps type → step_type gemappt', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        type: 'proposal',
        steps: [
          { type: 'dedup' },
          { type: 'impute_missing', params: { strategy: 'median' } },
        ],
        explanation: 'Ich schlage folgende Schritte vor.',
        confirmation_required: true,
      }),
    )

    const result = await sendRealMessage('http://localhost:8000', {
      userText: 'mach was',
      sessionId: 'session-abc',
    })

    expect(result).toEqual({
      sessionId: 'session-abc',
      response: {
        type: 'proposal',
        message: 'Ich schlage folgende Schritte vor.',
        steps: [
          { step_type: 'dedup' },
          { step_type: 'impute_missing', parameters_summary: 'strategy=median' },
        ],
      },
    })
  })

  it('Backend result: explanation → message, status standardmäßig done', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        type: 'result',
        run_id: 'run-42',
        explanation: 'Pipeline erfolgreich ausgeführt.',
      }),
    )

    const result = await sendRealMessage('http://localhost:8000', {
      userText: 'ausführen',
      sessionId: 'session-abc',
    })

    expect(result).toEqual({
      sessionId: 'session-abc',
      response: {
        type: 'result',
        message: 'Pipeline erfolgreich ausgeführt.',
        status: 'done',
      },
    })
  })

  it('Backend error (HTTP 422): error_code → details gemappt', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          type: 'error',
          message: 'LLM-Service nicht konfiguriert.',
          error_code: 'llm_not_configured',
        },
        { status: 422 },
      ),
    )

    const result = await sendRealMessage('http://localhost:8000', {
      userText: 'hallo',
      sessionId: 'session-abc',
    })

    expect(result).toEqual({
      sessionId: 'session-abc',
      response: {
        type: 'error',
        message: 'LLM-Service nicht konfiguriert.',
        details: 'llm_not_configured',
      },
    })
  })
})
