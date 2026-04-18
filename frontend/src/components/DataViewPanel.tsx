import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { fetchRawData, fetchRunData } from '../api/dataApi'
import type { ColumnStats, DataApiResponse } from '../api/dataApi'
import { ColumnSummaryHeader } from './ColumnSummaryHeader'
import { getFrontendEnv } from '../env'

type DataViewPanelProps = {
  activeDataRunId: string | null
  sessionId: string | null
  backendBaseUrl: string
}

export function DataViewPanel({ activeDataRunId, sessionId, backendBaseUrl }: DataViewPanelProps) {
  const [columns, setColumns] = useState<string[]>([])
  const [rows, setRows] = useState<unknown[][]>([])
  const [totalRows, setTotalRows] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isSplit, setIsSplit] = useState(false)
  // DV-2.3 — stats used for Summary-Header rendering
  const [columnStats, setColumnStats] = useState<Record<string, ColumnStats> | null>(null)

  const sentinelRef = useRef<HTMLDivElement>(null)
  const loadMoreRef = useRef<(() => void) | null>(null)
  const rowsRef = useRef<unknown[][]>([])
  // Tracks the "current" run ID — used to discard stale fetch responses after a run-ID change
  const currentRunRef = useRef<string | null>(null)

  const { useMock } = getFrontendEnv()

  // Keep rowsRef in sync so loadMore always has current offset
  useEffect(() => {
    rowsRef.current = rows
  }, [rows])

  const loadMore = useCallback(() => {
    if (!sessionId || isLoading || !hasMore) return

    const capturedRunId = activeDataRunId
    const capturedSessionId = sessionId
    const refKey = capturedRunId ?? '__raw__'
    const currentOffset = rowsRef.current.length
    setIsLoading(true)
    setError(null)

    const fetchFn = capturedRunId
      ? fetchRunData(backendBaseUrl, capturedSessionId, capturedRunId, currentOffset, 100)
      : fetchRawData(backendBaseUrl, capturedSessionId, currentOffset, 100)

    void fetchFn
      .then((data: DataApiResponse) => {
        if (currentRunRef.current !== refKey) return // stale response — discard
        setRows((prev) => {
          const updated = [...prev, ...data.rows]
          if (updated.length >= data.total_rows) {
            setHasMore(false)
          }
          return updated
        })
      })
      .catch((err: unknown) => {
        if (currentRunRef.current !== refKey) return // stale — discard
        setError(err instanceof Error ? err.message : 'Fehler beim Nachladen.')
      })
      .finally(() => {
        if (currentRunRef.current === refKey) {
          setIsLoading(false)
        }
      })
  }, [activeDataRunId, sessionId, backendBaseUrl, isLoading, hasMore])

  // Always keep loadMoreRef pointing to latest loadMore (never stale in observer)
  useEffect(() => {
    loadMoreRef.current = loadMore
  })

  // Reset and initial load when activeDataRunId or sessionId changes
  useEffect(() => {
    if (!sessionId || useMock) return

    const capturedRunId = activeDataRunId
    const capturedSessionId = sessionId
    const refKey = capturedRunId ?? '__raw__'
    currentRunRef.current = refKey // mark as current — invalidates all in-flight requests

    setColumns([])
    setRows([])
    rowsRef.current = []
    setTotalRows(0)
    setHasMore(false)
    setError(null)
    setIsSplit(false)
    setColumnStats(null)
    setIsLoading(true)

    const fetchFn = capturedRunId
      ? fetchRunData(backendBaseUrl, capturedSessionId, capturedRunId, 0, 1000)
      : fetchRawData(backendBaseUrl, capturedSessionId, 0, 1000)

    void fetchFn
      .then((data: DataApiResponse) => {
        if (currentRunRef.current !== refKey) return // stale response — discard
        setColumns(data.columns)
        setRows(data.rows)
        rowsRef.current = data.rows
        setTotalRows(data.total_rows)
        setHasMore(data.rows.length < data.total_rows)
        setIsSplit(data.is_split)
        if (data.column_stats) {
          setColumnStats(data.column_stats)
        }
      })
      .catch((err: unknown) => {
        if (currentRunRef.current !== refKey) return // stale — discard
        setError(err instanceof Error ? err.message : 'Fehler beim Laden der Daten.')
      })
      .finally(() => {
        if (currentRunRef.current === refKey) {
          setIsLoading(false)
        }
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDataRunId, sessionId])

  // IntersectionObserver for infinite scroll — re-created when hasMore/isLoading change
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasMore && !isLoading) {
          loadMoreRef.current?.()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasMore, isLoading])

  if (!sessionId) {
    return (
      <div className="dataViewPanel dataViewPanel--empty">
        Noch keine Session aktiv.
      </div>
    )
  }

  if (useMock) {
    return (
      <div className="dataViewPanel">
        <p className="dataViewPanel--empty">Datenansicht nicht verfügbar im Mock-Modus.</p>
      </div>
    )
  }

  return (
    <div className="dataViewPanel">
      <div className="dataViewToolbar">
        {isSplit && <span className="splitBadge">Split durchgeführt</span>}
        {rows.length > 0 && (
          <span className="dataViewInfo">
            1–{rows.length} von {totalRows.toLocaleString('de-DE')} Zeilen
          </span>
        )}
        {sessionId ? (
          <a
            className="csvDownloadButton"
            href={
              activeDataRunId
                ? `${backendBaseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(activeDataRunId)}/data/download`
                : `${backendBaseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/raw-data/download`
            }
            download
          >
            ⬇ CSV herunterladen
          </a>
        ) : (
          <span className="csvDownloadButton csvDownloadButton--disabled" aria-disabled="true">
            ⬇ CSV herunterladen
          </span>
        )}
      </div>
      <div className="dataTableContainer">
        <table className="dataTable">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>
                  <ColumnSummaryHeader
                    colName={col}
                    stats={columnStats?.[col]}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {(row as unknown[]).map((cell, colIndex) => (
                  <td key={colIndex}>{renderCell(cell)}</td>
                ))}
              </tr>
            ))}
            {isLoading && columns.length > 0 && (
              <tr>
                <td colSpan={columns.length} className="dataTableStatusRow">
                  Lade Daten …
                </td>
              </tr>
            )}
            {error && !isLoading && (
              <tr>
                <td colSpan={columns.length || 1} className="dataTableStatusRow dataTableErrorRow">
                  Fehler: {error}
                </td>
              </tr>
            )}
            {!hasMore && rows.length > 0 && !isLoading && (
              <tr>
                <td colSpan={columns.length || 1} className="dataTableStatusRow">
                  Alle Zeilen geladen
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div ref={sentinelRef} style={{ height: 1 }} />
      </div>
    </div>
  )
}

function renderCell(value: unknown): ReactNode {
  if (value === null || value === undefined) {
    return <em className="missingValue">Missing value</em>
  }
  const str = String(value)
  if (str === 'NaN' || str === 'null') {
    return <em className="missingValue">Missing value</em>
  }
  return str
}
