import type { ProposalResponse } from '../types'

export function countConfirmableProposalSteps(proposal: ProposalResponse): number {
  return proposal.steps.filter((step) => step.enabled !== false).length
}

export function canDirectlyConfirmProposal(proposal: ProposalResponse): boolean {
  return countConfirmableProposalSteps(proposal) === 1
}