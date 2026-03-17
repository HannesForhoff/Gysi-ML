import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import type { Dispatch } from 'react'

import type { ChatAction } from '../state/chatReducer'
import type { TransportInfo } from '../state/chatReducer'

// healthApi wird gemockt
vi.mock('../api/healthApi', () => ({
  fetchHealth: vi.fn(),
  fetchSpecSummary: vi.fn(),
}))

import { fetchHealth } from '../api/healthApi'

const MOCK_TRANSPORT: TransportInfo = { useMock: true, backendBaseUrl: '' }
const REAL_TRANSPORT: TransportInfo = {
  useMock: false,
  backendBaseUrl: 'http://localhost:8000',
}

describe('useHealthPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('Mock-Modus: kein fetch, keine Dispatch-Calls nach Interval', async () => {
    const { useHealthPolling } = await import('./useHealthPolling')
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useHealthPolling(dispatch, MOCK_TRANSPORT))

    await vi.advanceTimersByTimeAsync(30_000)

    expect(fetchHealth).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()
  })

  it('Real-Modus: fetchHealth wird nach erstem Interval aufgerufen', async () => {
    const { useHealthPolling } = await import('./useHealthPolling')
    vi.mocked(fetchHealth).mockResolvedValue(true)
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useHealthPolling(dispatch, REAL_TRANSPORT))

    await vi.advanceTimersByTimeAsync(10_000)

    expect(fetchHealth).toHaveBeenCalledWith('http://localhost:8000')
  })

  it('Health-Failure → HEALTH_CHECK_FAILED dispatched', async () => {
    const { useHealthPolling } = await import('./useHealthPolling')
    vi.mocked(fetchHealth).mockResolvedValue(false)
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useHealthPolling(dispatch, REAL_TRANSPORT))

    await vi.advanceTimersByTimeAsync(10_000)

    expect(dispatch).toHaveBeenCalledWith({ type: 'HEALTH_CHECK_FAILED' })
  })

  it('Recovery nach Failure → HEALTH_CHECK_RECOVERED dispatched', async () => {
    const { useHealthPolling } = await import('./useHealthPolling')
    vi.mocked(fetchHealth)
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true)
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useHealthPolling(dispatch, REAL_TRANSPORT))

    await vi.advanceTimersByTimeAsync(10_000)
    expect(dispatch).toHaveBeenCalledWith({ type: 'HEALTH_CHECK_FAILED' })

    await vi.advanceTimersByTimeAsync(10_000)
    expect(dispatch).toHaveBeenCalledWith({ type: 'HEALTH_CHECK_RECOVERED' })
  })

  it('Kein HEALTH_CHECK_RECOVERED wenn bisher kein Fehler', async () => {
    const { useHealthPolling } = await import('./useHealthPolling')
    vi.mocked(fetchHealth).mockResolvedValue(true)
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useHealthPolling(dispatch, REAL_TRANSPORT))

    await vi.advanceTimersByTimeAsync(30_000)

    const calls = vi.mocked(dispatch).mock.calls.map((c) => c[0])
    expect(calls.some((a) => a.type === 'HEALTH_CHECK_RECOVERED')).toBe(false)
  })
})
