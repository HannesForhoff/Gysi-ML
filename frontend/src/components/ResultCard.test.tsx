import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ResultResponse } from '../types'
import { ResultCard } from './ResultCard'

const doneResult: ResultResponse = {
  type: 'result',
  message: 'Run abgeschlossen.',
  status: 'done',
  metrics: { rmse: 123.45, r2: 0.89 },
  artifacts: [
    { id: 'plot-1', label: 'Plot (Placeholder)', url: '/favicon.svg', media_type: 'image/svg+xml' },
    { id: 'metrics-1', label: 'Metrics (JSON)', url: '/mock/metrics.json', media_type: 'application/json' },
  ],
}

const failedResult: ResultResponse = {
  type: 'result',
  message: 'Out of memory',
  status: 'failed',
}

describe('ResultCard — Status-Label', () => {
  it('rendert Status-Label „Ergebnis" bei status done', () => {
    render(<ResultCard result={doneResult} />)
    expect(screen.getByText('Ergebnis')).toBeInTheDocument()
  })

  it('rendert Status-Label „Fehlgeschlagen" bei status failed', () => {
    render(<ResultCard result={failedResult} />)
    expect(screen.getByText('Fehlgeschlagen')).toBeInTheDocument()
  })
})

describe('ResultCard — Metriken', () => {
  it('rendert Metriken als Key/Value', () => {
    render(<ResultCard result={doneResult} />)
    expect(screen.getByText('rmse')).toBeInTheDocument()
    expect(screen.getByText('123.45')).toBeInTheDocument()
    expect(screen.getByText('r2')).toBeInTheDocument()
    expect(screen.getByText('0.89')).toBeInTheDocument()
  })

  it('rendert keinen Metriken-Block wenn metrics fehlt', () => {
    const noMetrics: ResultResponse = {
      type: 'result',
      message: 'Fertig.',
      status: 'done',
    }
    const { container } = render(<ResultCard result={noMetrics} />)
    expect(container.querySelector('.resultMetrics')).not.toBeInTheDocument()
  })

  it('rendert keinen Metriken-Block wenn metrics leer ist', () => {
    const emptyMetrics: ResultResponse = {
      type: 'result',
      message: 'Fertig.',
      status: 'done',
      metrics: {},
    }
    const { container } = render(<ResultCard result={emptyMetrics} />)
    expect(container.querySelector('.resultMetrics')).not.toBeInTheDocument()
  })
})

describe('ResultCard — Artefakte', () => {
  it('rendert Artefakte-Liste mit Label und Media-Type', () => {
    render(<ResultCard result={doneResult} />)
    expect(screen.getByText('Plot (Placeholder)')).toBeInTheDocument()
    expect(screen.getByText('(image/svg+xml)')).toBeInTheDocument()
    expect(screen.getByText('Metrics (JSON)')).toBeInTheDocument()
    expect(screen.getByText('(application/json)')).toBeInTheDocument()
  })

  it('rendert Artefakte als klickbare Links mit target="_blank"', () => {
    render(<ResultCard result={doneResult} />)
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('href', '/favicon.svg')
    expect(links[0]).toHaveAttribute('target', '_blank')
    expect(links[1]).toHaveAttribute('href', '/mock/metrics.json')
    expect(links[1]).toHaveAttribute('target', '_blank')
  })

  it('rendert ungültige URLs als Nur-Text mit Hinweis', () => {
    const invalidArtifact: ResultResponse = {
      type: 'result',
      message: 'Fertig.',
      status: 'done',
      artifacts: [
        { id: 'bad-1', label: 'Böses Artefakt', url: 'javascript:alert(1)', media_type: 'text/html' },
      ],
    }
    render(<ResultCard result={invalidArtifact} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText(/Böses Artefakt \(ungültige URL\)/)).toBeInTheDocument()
  })

  it('rendert keine Artefakte-Liste wenn artifacts fehlt', () => {
    const { container } = render(<ResultCard result={failedResult} />)
    expect(container.querySelector('.resultArtifacts')).not.toBeInTheDocument()
  })

  it('rendert keine Artefakte-Liste wenn artifacts leer ist', () => {
    const emptyArtifacts: ResultResponse = {
      type: 'result',
      message: 'Fertig.',
      status: 'done',
      artifacts: [],
    }
    const { container } = render(<ResultCard result={emptyArtifacts} />)
    expect(container.querySelector('.resultArtifacts')).not.toBeInTheDocument()
  })
})

describe('ResultCard — Message', () => {
  it('rendert Message-Text wenn vorhanden', () => {
    render(<ResultCard result={doneResult} />)
    expect(screen.getByText('Run abgeschlossen.')).toBeInTheDocument()
  })

  it('rendert error_message-Text bei failed', () => {
    render(<ResultCard result={failedResult} />)
    expect(screen.getByText('Out of memory')).toBeInTheDocument()
  })
})

describe('ResultCard — CSS-Klassen', () => {
  it('hat CSS-Klasse resultCard--done bei status done', () => {
    const { container } = render(<ResultCard result={doneResult} />)
    expect(container.firstChild).toHaveClass('resultCard--done')
  })

  it('hat CSS-Klasse resultCard--failed bei status failed', () => {
    const { container } = render(<ResultCard result={failedResult} />)
    expect(container.firstChild).toHaveClass('resultCard--failed')
  })
})
