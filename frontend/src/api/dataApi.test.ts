import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchRunData } from './dataApi'

describe('fetchRunData', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('baut korrekte URL mit encoded sessionId/runId und Query-Params', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        columns: ['a', 'b'],
        rows: [[1, 2]],
        total_rows: 1,
        offset: 0,
        limit: 1000,
        is_split: false,
      }),
    } as Response)

    await fetchRunData('http://localhost:8000/', 'a/b', 'c d', 0, 1000)

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/sessions/a%2Fb/runs/c%20d/data?offset=0&limit=1000',
    )
  })

  it('parst valide Response korrekt', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        columns: ['season', 'yr'],
        rows: [
          [1, 0],
          [2, 1],
        ],
        total_rows: 100,
        offset: 0,
        limit: 1000,
        is_split: false,
      }),
    } as Response)

    const result = await fetchRunData('http://localhost:8000', 'sess-1', 'run-1', 0, 1000)

    expect(result.columns).toEqual(['season', 'yr'])
    expect(result.rows).toHaveLength(2)
    expect(result.total_rows).toBe(100)
    expect(result.is_split).toBe(false)
    expect(result.column_stats).toBeUndefined()
  })

  it('enthält column_stats bei offset=0, fehlt bei offset>0', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          columns: ['season'],
          rows: [[1]],
          total_rows: 200,
          offset: 0,
          limit: 1000,
          is_split: false,
          column_stats: {
            season: { missing_count: 0, missing_pct: 0, distinct_count: 4, distinct_pct: 0.02 },
          },
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          columns: ['season'],
          rows: [[2]],
          total_rows: 200,
          offset: 100,
          limit: 100,
          is_split: false,
        }),
      } as Response)

    const r1 = await fetchRunData('http://localhost:8000', 's', 'r', 0, 1000)
    expect(r1.column_stats).toBeDefined()
    expect(r1.column_stats!['season'].distinct_count).toBe(4)

    const r2 = await fetchRunData('http://localhost:8000', 's', 'r', 100, 100)
    expect(r2.column_stats).toBeUndefined()
  })

  it('wirft bei HTTP 404', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)

    await expect(
      fetchRunData('http://localhost:8000', 'sess-1', 'run-1', 0, 100),
    ).rejects.toThrow('HTTP 404')
  })

  it('wirft bei malformierter Response (kein Objekt)', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => 'not an object',
    } as Response)

    await expect(
      fetchRunData('http://localhost:8000', 'sess-1', 'run-1', 0, 100),
    ).rejects.toThrow('kein Objekt')
  })

  it('wirft wenn columns fehlt', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ rows: [], total_rows: 0, offset: 0, limit: 100, is_split: false }),
    } as Response)

    await expect(
      fetchRunData('http://localhost:8000', 'sess-1', 'run-1', 0, 100),
    ).rejects.toThrow('columns fehlt')
  })
})
