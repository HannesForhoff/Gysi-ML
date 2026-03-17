import { useEffect, useRef } from 'react'
import type { Dispatch } from 'react'

import { fetchHealth } from '../api/healthApi'
import type { ChatAction, TransportInfo } from '../state/chatReducer'

const POLL_INTERVAL_MS = 10_000

export function useHealthPolling(
  dispatch: Dispatch<ChatAction>,
  transport: TransportInfo,
): void {
  const hasFailed = useRef(false)

  useEffect(() => {
    if (transport.useMock) return

    const baseUrl = transport.backendBaseUrl

    async function check() {
      if (document.visibilityState === 'hidden') return

      const healthy = await fetchHealth(baseUrl)

      if (!healthy) {
        hasFailed.current = true
        dispatch({ type: 'HEALTH_CHECK_FAILED' })
      } else if (hasFailed.current) {
        hasFailed.current = false
        dispatch({ type: 'HEALTH_CHECK_RECOVERED' })
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
