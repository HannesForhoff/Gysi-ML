import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchRunStatus } from './runApi'

describe('fetchRunStatus', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('gibt RunStatusResponse für done zurück', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'done',
        metrics: { rmse: 123.45, r2: 0.89 },
        artifacts: [
          { artifact_id: 'plot-1', type: 'plot', href: '/v1/artifacts/plot-1' },
        ],
      }),
    } as Response)

    const result = await fetchRunStatus('http://localhost:8000', 'sess-1', 'run-1')

    expect(result.status).toBe('done')
    expect(result.metrics).toEqual({ rmse: 123.45, r2: 0.89 })
    expect(result.artifacts).toHaveLength(1)
    expect(result.artifacts![0].id).toBe('plot-1')
    expect(result.artifacts![0].url).toBe('/v1/artifacts/plot-1')
  })

  it('gibt RunStatusResponse für running zurück', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'running' }),
    } as Response)

    const result = await fetchRunStatus('http://localhost:8000', 'sess-1', 'run-1')

    expect(result.status).toBe('running')
    expect(result.metrics).toBeUndefined()
    expect(result.artifacts).toBeUndefined()
  })

  it('gibt RunStatusResponse für failed mit error_message zurück', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'failed',
        error_message: 'Out of memory',
      }),
    } as Response)

    const result = await fetchRunStatus('http://localhost:8000', 'sess-1', 'run-1')

    expect(result.status).toBe('failed')
    expect(result.error_message).toBe('Out of memory')
  })

  it('wirft bei HTTP-Fehler', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)

    await expect(
      fetchRunStatus('http://localhost:8000', 'sess-1', 'run-1'),
    ).rejects.toThrow('HTTP 404')
  })

  it('wirft bei ungültigem Status', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'invalid' }),
    } as Response)

    await expect(
      fetchRunStatus('http://localhost:8000', 'sess-1', 'run-1'),
    ).rejects.toThrow('Ungültiger Run-Status')
  })

  it('encodiert sessionId und runId in der URL', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'queued' }),
    } as Response)

    await fetchRunStatus('http://localhost:8000/', 'a/b', 'c d')

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/sessions/a%2Fb/runs/c%20d',
    )
  })

  it('mappt Backend artifact_id/href auf Frontend id/url', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'done',
        artifacts: [
          {
            artifact_id: 'a1',
            label: 'My Plot',
            type: 'image/png',
            href: '/v1/artifacts/a1',
            media_type: 'image/png',
          },
        ],
      }),
    } as Response)

    const result = await fetchRunStatus('http://localhost:8000', 's', 'r')

    expect(result.artifacts![0]).toEqual({
      id: 'a1',
      label: 'My Plot',
      url: '/v1/artifacts/a1',
      media_type: 'image/png',
    })
  })

  it('wirft bei Netzwerkfehler', async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(
      fetchRunStatus('http://localhost:8000', 's', 'r'),
    ).rejects.toThrow('Failed to fetch')
  })

  it('mappt Backend-Status "completed" auf "done"', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'completed',
        metrics: { rmse: 1.0 },
      }),
    } as Response)

    const result = await fetchRunStatus('http://localhost:8000', 's', 'r')

    expect(result.status).toBe('done')
    expect(result.metrics).toEqual({ rmse: 1.0 })
  })

  it('konstruiert URL aus artifact_id wenn href und url fehlen', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'done',
        artifacts: [
          {
            artifact_id: '550e8400-e29b-41d4-a716-446655440000',
            type: 'plot',
          },
        ],
      }),
    } as Response)

    const result = await fetchRunStatus('http://localhost:8000', 's', 'r')

    expect(result.artifacts).toHaveLength(1)
    expect(result.artifacts![0].id).toBe('550e8400-e29b-41d4-a716-446655440000')
    expect(result.artifacts![0].url).toBe('http://localhost:8000/v1/artifacts/550e8400-e29b-41d4-a716-446655440000')
    expect(result.artifacts![0].label).toBe('plot')
  })
})
