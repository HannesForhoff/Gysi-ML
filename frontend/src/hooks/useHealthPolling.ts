import { useEffect } from 'react'
import type { Dispatch } from 'react'

import { fetchHealth } from '../api/healthApi'
import type { ChatAction, TransportInfo } from '../state/chatReducer'

const POLL_INTERVAL_MS = 10_000

export function useHealthPolling(
  dispatch: Dispatch<ChatAction>,
  transport: TransportInfo,
): void {
  useEffect(() => {
    if (transport.useMock) return

    const baseUrl = transport.backendBaseUrl

    async function check() {
      if (document.visibilityState === 'hidden') return

      const result = await fetchHealth(baseUrl)

      // Immer dispatchen: der Reducer ignoriert RECOVERED wenn nicht backend_unreachable
      // (idempotent), verhindert aber Stuck-State nach SEND_REQUEST_FAILED
      if (!result.healthy) {
        dispatch({ type: 'HEALTH_CHECK_FAILED' })
      } else {
        dispatch({ type: 'HEALTH_CHECK_RECOVERED', llmModel: result.llmModel })
      }
    }

    const id = setInterval(() => {
      void check()
    }, POLL_INTERVAL_MS)

    return () => {
      clearInterval(id)
    }
  }, [dispatch, transport.useMock, transport.backendBaseUrl])
}
