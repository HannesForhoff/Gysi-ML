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
})
