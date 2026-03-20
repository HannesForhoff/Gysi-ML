import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchSpecSummary } from './healthApi'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('fetchSpecSummary', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('mappt Backend-SpecVersionResponse (version + spec.steps) korrekt', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          spec_id: 'abc',
          session_id: 'sess-1',
          version: 'v1',
          created_at: '2026-03-20T00:00:00Z',
          spec: {
            steps: [
              { type: 'dedup', enabled: true },
              { type: 'imputation', enabled: false },
            ],
          },
        }),
      ),
    )

    const result = await fetchSpecSummary('http://localhost:8000', 'sess-1')

    expect(result).toEqual({
      spec_version_id: 'v1',
      steps: [
        { step_type: 'dedup', enabled: true },
        { step_type: 'imputation', enabled: false },
      ],
    })
  })

  it('Step ohne enabled-Feld → enabled: true (Default)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          version: 'v2',
          spec: {
            steps: [{ type: 'encoding' }],
          },
        }),
      ),
    )

    const result = await fetchSpecSummary('http://localhost:8000', 'sess-1')

    expect(result?.steps[0]).toEqual({ step_type: 'encoding', enabled: true })
  })

  it('HTTP 404 → null', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ error: 'spec_not_found' }, 404),
      ),
    )

    const result = await fetchSpecSummary('http://localhost:8000', 'sess-1')
    expect(result).toBeNull()
  })

  it('Network-Error → null (kein Throw)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const result = await fetchSpecSummary('http://localhost:8000', 'sess-1')
    expect(result).toBeNull()
  })

  it('session_id wird URL-encoded übergeben', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ version: 'v1', spec: { steps: [] } }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchSpecSummary('http://localhost:8000', 'sess/with spaces')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/v1/sessions/sess%2Fwith%20spaces/spec',
    )
  })
})
