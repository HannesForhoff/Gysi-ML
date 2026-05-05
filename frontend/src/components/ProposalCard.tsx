import type { ProposalResponse } from '../types'
import { getStepLabel, STEP_LABELS } from '../utils/stepMeta'

type ProposalCardProps = {
  proposal: ProposalResponse
  onConfirm: (proposalId: string) => void
  disabled?: boolean
  isActive?: boolean
}

export function ProposalCard({ proposal, onConfirm, disabled, isActive = true }: ProposalCardProps) {
  return (
    <div className={`proposalCard${!isActive ? ' proposalCard--superseded' : ''}`}>
      <div className="proposalLabel">
        {isActive ? 'Vorschlag (noch nicht ausgeführt)' : 'Vorschlag (nicht bestätigt)'}
      </div>
      {proposal.data_leakage_warning && (
        <div className="proposalLeakageWarning">
          <span className="proposalLeakageWarningIcon">⚠</span>
          <div className="proposalLeakageWarningText">
            <strong>Data-Leakage-Risiko erkannt!</strong>
            {' '}Die folgenden Schritte würden <em>vor</em> dem Train/Test-Split
            ausgeführt und lernen dabei aus dem vollständigen Datensatz — auch
            aus den späteren Testdaten:
            {' '}<strong>
              {(proposal.leakage_steps ?? []).map((t) => STEP_LABELS[t] ?? t).join(', ')}
            </strong>.
            {' '}Bitte bestätige bewusst oder passe die Pipeline-Reihenfolge an
            (Split vor diese Schritte setzen).
          </div>
        </div>
      )}
      {proposal.message && (
        <div className="proposalMessage">{proposal.message}</div>
      )}
      <ul className="proposalSteps">
        {proposal.steps.map((step, idx) => (
          <li key={`${step.step_type}-${idx}`} className="proposalStep">
            <span className="proposalStepNum">{idx + 1}</span>
            <div className="proposalStepBody">
              <span className="proposalStepName">{getStepLabel(step.step_type)}</span>
              {step.parameters_summary && (
                <span className="proposalStepParams">{step.parameters_summary}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
      {isActive && (
        <button
          type="button"
          className="proposalConfirmButton"
          onClick={() => onConfirm(proposal.proposal_id ?? '')}
          disabled={disabled}
          aria-disabled={disabled}
        >
          Bestätigen &amp; Ausführen
        </button>
      )}
    </div>
  )
}
