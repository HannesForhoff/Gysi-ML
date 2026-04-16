import { useState } from 'react'
import { createPortal } from 'react-dom'

import type { ColumnStats } from '../api/dataApi'

type ColumnSummaryHeaderProps = {
  colName: string
  stats: ColumnStats | undefined
}

type TooltipState = { index: number; x: number; y: number }

function HistogramSvg({ histogram }: { histogram: NonNullable<ColumnStats['histogram']> }) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const maxCount = Math.max(...histogram.counts, 1)

  const handleMouseEnter = (i: number, e: React.MouseEvent) => {
    setTooltip({ index: i, x: e.clientX, y: e.clientY })
  }
  const handleMouseMove = (i: number, e: React.MouseEvent) => {
    setTooltip({ index: i, x: e.clientX, y: e.clientY })
  }
  const handleMouseLeave = () => setTooltip(null)

  const tooltipEl = tooltip !== null ? (() => {
    const count = histogram.counts[tooltip.index] ?? 0
    const binFrom = histogram.bins[tooltip.index]
    const binTo = histogram.bins[tooltip.index + 1]
    const isDiscrete = binTo !== undefined && binTo - (binFrom ?? 0) === 1 && Number.isInteger(binFrom)
    const rangeLabel = isDiscrete
      ? formatBin(binFrom)
      : `${formatBin(binFrom)} – ${formatBin(binTo)}`
    return (
      <div
        className="histogramTooltip"
        style={{ left: tooltip.x + 14, top: tooltip.y - 64 }}
      >
        <span className="histogramTooltipRange">{rangeLabel}</span>
        <span className="histogramTooltipCount">
          <span className="histogramTooltipDot" />
          Count: <strong>{count.toLocaleString('de-DE')}</strong>
        </span>
      </div>
    )
  })() : null

  return (
    <>
      <svg width="100%" height="40" viewBox="0 0 100 40" preserveAspectRatio="none">
        {histogram.counts.map((count, i) => {
          const n = histogram.counts.length
          const slotWidth = 100 / n
          const barHeight = Math.max((count / maxCount) * 40, count > 0 ? 2 : 0)
          const isHovered = tooltip?.index === i
          return (
            <rect
              key={i}
              x={i * slotWidth + 0.5}
              y={40 - barHeight}
              width={slotWidth - 1}
              height={barHeight}
              fill={isHovered ? '#90cdf4' : '#4299e1'}
              onMouseEnter={(e) => handleMouseEnter(i, e)}
              onMouseMove={(e) => handleMouseMove(i, e)}
              onMouseLeave={handleMouseLeave}
              style={{ cursor: 'default' }}
            />
          )
        })}
      </svg>
      {tooltipEl !== null && createPortal(tooltipEl, document.body)}
    </>
  )
}

function formatBin(value: number | undefined): string {
  if (value === undefined) return ''
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function ColumnSummaryHeader({ colName, stats }: ColumnSummaryHeaderProps) {
  if (stats === undefined) {
    return <span className="columnSummaryName">{colName}</span>
  }

  return (
    <div className="columnSummaryHeader">
      <span className="columnSummaryName">{colName}</span>
      {stats.histogram !== undefined && <HistogramSvg histogram={stats.histogram} />}
      <span className="columnSummaryStat">
        Missing: {stats.missing_count} ({stats.missing_pct.toFixed(1)}%)
      </span>
      <span className="columnSummaryStat">
        Distinct: {stats.distinct_count} ({stats.distinct_pct.toFixed(1)}%)
      </span>
      {stats.min !== undefined && stats.max !== undefined && (
        <div className="columnSummaryMinMax">
          <span>Min {stats.min}</span>
          <span>Max {stats.max}</span>
        </div>
      )}
    </div>
  )
}
