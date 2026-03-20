import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusPanel } from './StatusPanel'

const BASE_PROPS = {
  transport: { useMock: false, backendBaseUrl: 'http://localhost:8000' },
  specSummary: null,
  lastRun: null,
  artifacts: [],
  lastError: null,
}

describe('StatusPanel — backend_unreachable', () => {
  it('zeigt handlungsfähige Copy bei backend_unreachable', () => {
    render(<StatusPanel {...BASE_PROPS} ui={{ type: 'backend_unreachable' }} />)

    expect(
      screen.getByText(
        'Backend nicht erreichbar. Bitte Backend starten oder URL prüfen.',
      ),
    ).toBeInTheDocument()
  })

  it('zeigt keinen Fehler-Block bei idle', () => {
    render(<StatusPanel {...BASE_PROPS} ui={{ type: 'idle' }} />)

    expect(
      screen.queryByText(/Backend nicht erreichbar/),
    ).not.toBeInTheDocument()
  })
})

describe('StatusPanel — validation_error', () => {
  it('zeigt Hinweis-Block bei validation_error', () => {
    render(<StatusPanel {...BASE_PROPS} ui={{ type: 'validation_error' }} />)

    expect(
      screen.getByText(
        'Validierungsfehler aufgetreten. Sieh dir die Fehlermeldung im Chat an und sende eine neue Nachricht.',
      ),
    ).toBeInTheDocument()
  })

  it('zeigt keinen Hinweis-Block bei idle', () => {
    render(<StatusPanel {...BASE_PROPS} ui={{ type: 'idle' }} />)

    expect(
      screen.queryByText(/Validierungsfehler aufgetreten/),
    ).not.toBeInTheDocument()
  })
})
