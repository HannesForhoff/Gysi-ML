import type { ProposalResponse } from '../types'

type ProposalCardProps = {
  proposal: ProposalResponse
  onConfirm: (proposalId: string) => void
  disabled?: boolean
}

export function ProposalCard({ proposal, onConfirm, disabled }: ProposalCardProps) {
  return (
    <div className="proposalCard">
      <div className="proposalLabel">Vorschlag (noch nicht ausgeführt)</div>
      {proposal.message && (
        <div className="proposalMessage">{proposal.message}</div>
      )}
      <ul className="proposalSteps">
        {proposal.steps.map((step, idx) => (
          <li key={`${step.step_type}-${idx}`} className="proposalStep">
            <span className="proposalStepType">{step.step_type}</span>
            {step.parameters_summary && (
              <span className="proposalStepParams">
                {' '}— {step.parameters_summary}
              </span>
            )}
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="proposalConfirmButton"
        onClick={() => onConfirm(proposal.proposal_id ?? '')}
        disabled={disabled}
        aria-disabled={disabled}
      >
        Bestätigen &amp; Ausführen
      </button>
    </div>
  )
}
