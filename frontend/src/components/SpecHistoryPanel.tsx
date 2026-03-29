import type { VersionTree } from '../types'

type SpecHistoryPanelProps = {
  sessionId: string | null
  specHistory: VersionTree | null
  onRollback: (targetSpecId: string) => void
  isRollingBack: boolean
  rollbackTargetId: string | null
}

function runStatusColor(status: string | null): string {
  if (status === 'done') return '#38a169'
  if (status === 'failed') return '#e53e3e'
  return '#cbd5e0'
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('de-DE', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function SpecHistoryPanel({
  sessionId,
  specHistory,
  onRollback,
  isRollingBack,
  rollbackTargetId,
}: SpecHistoryPanelProps) {
  if (!sessionId) {
    return (
      <>
        <div className="historyHeader">Spec-Verlauf</div>
        <div className="historyEmpty">Keine Session aktiv</div>
      </>
    )
  }

  if (!specHistory || specHistory.versions.length === 0) {
    return (
      <>
        <div className="historyHeader">Spec-Verlauf</div>
        <div className="historyEmpty">Noch keine Versionen</div>
      </>
    )
  }

  const versions = [...specHistory.versions].reverse()
  const activeId = specHistory.active_spec_id

  return (
    <>
      <div className="historyHeader">Spec-Verlauf</div>
      <ul className="historyList">
        {versions.map((v) => {
          const isActive = v.spec_id === activeId
          const isPending = isRollingBack && rollbackTargetId === v.spec_id
          return (
            <li key={v.spec_id} className={`historyEntry${isActive ? ' historyEntry--active' : ''}`}>
              <div className="historyEntryRow">
                <span className="historyVersion">{v.version}</span>
                <span
                  className="historyRunDot"
                  style={{ background: runStatusColor(v.last_run_status) }}
                  title={v.last_run_status ?? 'kein Run'}
                />
              </div>
              {v.change_summary && (
                <div className="historyChangeSummary">{v.change_summary}</div>
              )}
              <div className="historyDate">{formatDate(v.created_at)}</div>
              {isActive ? (
                <div className="historyActiveBadge">Aktiv</div>
              ) : (
                <button
                  className="historyRollbackBtn"
                  onClick={() => { onRollback(v.spec_id) }}
                  disabled={isRollingBack}
                  title={`Zu ${v.version} zurückrollen`}
                >
                  {isPending ? '…' : '↩ Rollback'}
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </>
  )
}
