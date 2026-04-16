import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ColumnStats } from '../api/dataApi'
import { ColumnSummaryHeader } from './ColumnSummaryHeader'

const numericStats: ColumnStats = {
  missing_count: 0,
  missing_pct: 0.0,
  distinct_count: 500,
  distinct_pct: 57.1,
  min: 1,
  max: 977,
  histogram: {
    bins: [1, 99, 197, 295, 393, 491, 589, 687, 785, 883, 977],
    counts: [50, 80, 120, 200, 180, 150, 100, 70, 40, 10],
  },
}

const categoricalStats: ColumnStats = {
  missing_count: 5,
  missing_pct: 0.6,
  distinct_count: 4,
  distinct_pct: 0.5,
}

describe('ColumnSummaryHeader — Spaltenname', () => {
  it('rendert Spaltenname bei numerischer Spalte', () => {
    render(<ColumnSummaryHeader colName="cnt" stats={numericStats} />)
    expect(screen.getByText('cnt')).toBeInTheDocument()
  })

  it('rendert Spaltenname bei kategorischer Spalte', () => {
    render(<ColumnSummaryHeader colName="season" stats={categoricalStats} />)
    expect(screen.getByText('season')).toBeInTheDocument()
  })
})

describe('ColumnSummaryHeader — SVG-Histogram', () => {
  it('rendert SVG mit 10 rect-Elementen bei numerischer Spalte', () => {
    const { container } = render(<ColumnSummaryHeader colName="cnt" stats={numericStats} />)
    const rects = container.querySelectorAll('svg rect')
    expect(rects).toHaveLength(10)
  })

  it('rendert kein SVG bei kategorischer Spalte', () => {
    const { container } = render(<ColumnSummaryHeader colName="season" stats={categoricalStats} />)
    const svg = container.querySelector('svg')
    expect(svg).not.toBeInTheDocument()
  })
})

describe('ColumnSummaryHeader — Missing und Distinct', () => {
  it('zeigt Missing: 0 (0.0%) korrekt an (AC #4)', () => {
    render(<ColumnSummaryHeader colName="cnt" stats={numericStats} />)
    expect(screen.getByText('Missing: 0 (0.0%)')).toBeInTheDocument()
  })

  it('zeigt Missing mit Wert > 0 korrekt an', () => {
    render(<ColumnSummaryHeader colName="season" stats={categoricalStats} />)
    expect(screen.getByText('Missing: 5 (0.6%)')).toBeInTheDocument()
  })

  it('zeigt Distinct korrekt an', () => {
    render(<ColumnSummaryHeader colName="cnt" stats={numericStats} />)
    expect(screen.getByText('Distinct: 500 (57.1%)')).toBeInTheDocument()
  })
})

describe('ColumnSummaryHeader — Min/Max', () => {
  it('zeigt Min und Max bei numerischer Spalte an', () => {
    render(<ColumnSummaryHeader colName="cnt" stats={numericStats} />)
    expect(screen.getByText('Min 1')).toBeInTheDocument()
    expect(screen.getByText('Max 977')).toBeInTheDocument()
  })

  it('zeigt kein Min/Max bei kategorischer Spalte an', () => {
    render(<ColumnSummaryHeader colName="season" stats={categoricalStats} />)
    expect(screen.queryByText(/Min/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Max/)).not.toBeInTheDocument()
  })
})

describe('ColumnSummaryHeader — Fallback', () => {
  it('rendert nur Spaltenname wenn stats === undefined (AC #6)', () => {
    const { container } = render(<ColumnSummaryHeader colName="dteday" stats={undefined} />)
    expect(screen.getByText('dteday')).toBeInTheDocument()
    expect(container.querySelector('svg')).not.toBeInTheDocument()
    expect(screen.queryByText(/Missing/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Distinct/)).not.toBeInTheDocument()
  })
})
