import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import type { Dispatch } from 'react'

import type { ChatAction, ChatState } from '../state/chatReducer'

vi.mock('../api/runApi', () => ({
  fetchRunStatus: vi.fn(),
}))

import { fetchRunStatus } from '../api/runApi'

function pollingState(overrides?: Partial<ChatState>): Pick<ChatState, 'ui' | 'runId' | 'sessionId' | 'transport'> {
  return {
    ui: { type: 'run_polling' },
    runId: 'run-001',
    sessionId: 'sess-1',
    transport: { useMock: false, backendBaseUrl: 'http://localhost:8000' },
    ...overrides,
  }
}

function mockState(): Pick<ChatState, 'ui' | 'runId' | 'sessionId' | 'transport'> {
  return {
    ui: { type: 'run_polling' },
    runId: 'run-mock',
    sessionId: 'sess-mock',
    transport: { useMock: true, backendBaseUrl: '' },
  }
}

describe('useRunPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('pollt nicht wenn ui !== run_polling', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() =>
      useRunPolling(dispatch, {
        ...pollingState(),
        ui: { type: 'idle' },
      }),
    )

    await vi.advanceTimersByTimeAsync(5_000)
    expect(fetchRunStatus).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()
  })

  it('pollt nicht wenn runId === null', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() =>
      useRunPolling(dispatch, {
        ...pollingState(),
        runId: null,
      }),
    )

    await vi.advanceTimersByTimeAsync(5_000)
    expect(fetchRunStatus).not.toHaveBeenCalled()
  })

  it('erster Poll nach 1s, dispatcht RUN_POLL_SUCCEEDED bei done', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus).mockResolvedValue({
      status: 'done',
      metrics: { rmse: 1.0 },
      artifacts: [],
    })
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, pollingState()))

    await vi.advanceTimersByTimeAsync(1_000)

    expect(fetchRunStatus).toHaveBeenCalledWith('http://localhost:8000', 'sess-1', 'run-001')
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'RUN_POLL_SUCCEEDED',
        status: 'done',
      }),
    )
  })

  it('Backoff: 1s → 2s → 4s bei running', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus).mockResolvedValue({ status: 'running' })
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, pollingState()))

    // 1s → first poll
    await vi.advanceTimersByTimeAsync(1_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(1)

    // 2s → second poll (at t=3s)
    await vi.advanceTimersByTimeAsync(2_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(2)

    // 4s → third poll (at t=7s)
    await vi.advanceTimersByTimeAsync(4_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(3)
  })

  it('Backoff cap bei 8s', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus).mockResolvedValue({ status: 'running' })
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, pollingState()))

    // 1s + 2s + 4s + 8s = 15s → 4 polls
    await vi.advanceTimersByTimeAsync(1_000)
    await vi.advanceTimersByTimeAsync(2_000)
    await vi.advanceTimersByTimeAsync(4_000)
    await vi.advanceTimersByTimeAsync(8_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(4)

    // Next should also be 8s (capped)
    await vi.advanceTimersByTimeAsync(8_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(5)
  })

  it('stoppt Polling bei done', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus)
      .mockResolvedValueOnce({ status: 'running' })
      .mockResolvedValueOnce({ status: 'done', metrics: { r2: 0.9 } })
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, pollingState()))

    // 1s → running
    await vi.advanceTimersByTimeAsync(1_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(1)

    // 2s → done
    await vi.advanceTimersByTimeAsync(2_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(2)

    // Kein weiterer Poll
    await vi.advanceTimersByTimeAsync(10_000)
    expect(fetchRunStatus).toHaveBeenCalledTimes(2)
  })

  it('dispatcht RUN_POLL_NETWORK_ERROR bei fetch-Fehler', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus).mockRejectedValue(new TypeError('Failed to fetch'))
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, pollingState()))

    await vi.advanceTimersByTimeAsync(1_000)

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'RUN_POLL_NETWORK_ERROR',
      }),
    )
  })

  it('dispatcht RUN_LONG_RUNNING nach 120s', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus).mockResolvedValue({ status: 'running' })
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, pollingState()))

    await vi.advanceTimersByTimeAsync(120_000)

    const longRunCall = (dispatch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call: unknown[]) =>
        (call[0] as { type: string }).type === 'RUN_LONG_RUNNING',
    )
    expect(longRunCall).toBeDefined()
  })

  it('Cleanup cancelt Timeouts bei Unmount', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus).mockResolvedValue({ status: 'running' })
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    const { unmount } = renderHook(() => useRunPolling(dispatch, pollingState()))

    unmount()

    await vi.advanceTimersByTimeAsync(5_000)

    // fetchRunStatus should not have been called after unmount
    expect(fetchRunStatus).not.toHaveBeenCalled()
  })

  it('Mock-Modus: 2 × running, dann done', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, mockState()))

    // Flush poll timeout (1s) + mock's internal setTimeout(0)
    await vi.advanceTimersByTimeAsync(1_001)
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'RUN_POLL_SUCCEEDED', status: 'running' }),
    )

    // Flush second poll (2s backoff) + mock setTimeout(0)
    await vi.advanceTimersByTimeAsync(2_001)

    // Flush third poll (4s backoff) + mock setTimeout(0)
    await vi.advanceTimersByTimeAsync(4_001)
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'RUN_POLL_SUCCEEDED', status: 'done' }),
    )

    // Mock-Modus nutzt nicht fetchRunStatus
    expect(fetchRunStatus).not.toHaveBeenCalled()
  })

  it('done-Poll enthält assistantMessage mit response-Feld', async () => {
    const { useRunPolling } = await import('./useRunPolling')
    vi.mocked(fetchRunStatus).mockResolvedValue({
      status: 'done',
      metrics: { rmse: 1.0 },
    })
    const dispatch = vi.fn() as unknown as Dispatch<ChatAction>

    renderHook(() => useRunPolling(dispatch, pollingState()))

    await vi.advanceTimersByTimeAsync(1_000)

    const doneCall = (dispatch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call: unknown[]) => {
        const action = call[0] as { type: string; status?: string }
        return action.type === 'RUN_POLL_SUCCEEDED' && action.status === 'done'
      },
    )
    expect(doneCall).toBeDefined()
    const action = doneCall![0] as { assistantMessage?: { role: string; response?: { type: string } } }
    expect(action.assistantMessage).toBeDefined()
    expect(action.assistantMessage!.role).toBe('assistant')
    expect(action.assistantMessage!.response?.type).toBe('result')
  })
})
