import type { VersionTree } from '../types'
import { VersionTreeGraph } from './VersionTreeGraph'

type SpecHistoryPanelProps = {
  sessionId: string | null
  specHistory: VersionTree | null
  onRollback: (targetSpecId: string) => void
  isRollingBack: boolean
  rollbackTargetId: string | null
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

  return (
    <>
      <div className="historyHeader">Spec-Verlauf</div>
      <VersionTreeGraph
        specHistory={specHistory}
        onRollback={onRollback}
        isRollingBack={isRollingBack}
        rollbackTargetId={rollbackTargetId}
      />
    </>
  )
}
