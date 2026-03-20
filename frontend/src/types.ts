export type ChatRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  ts: string
  response?: AssistantResponse
}

export interface SpecStepSummary {
  step_type: string
  enabled: boolean
}

export interface SpecSummary {
  spec_version_id: string
  steps: SpecStepSummary[]
  notes?: string
}

export interface ArtifactRef {
  id: string
  label: string
  url: string
  media_type: string
}

export interface ProposalStep {
  step_type: string
  enabled?: boolean
  parameters_summary?: string
}

export interface ProposalResponse {
  type: 'proposal'
  message: string
  steps: ProposalStep[]
  parameters_summary?: string
  spec_summary?: SpecSummary
  proposal_id?: string
}

export interface ResultResponse {
  type: 'result'
  message: string
  status: 'done' | 'failed'
  metrics?: Record<string, number | string>
  artifacts?: ArtifactRef[]
  spec_summary?: SpecSummary
}

export interface ErrorResponse {
  type: 'error'
  message: string
  details?: string
}

export interface SpecUpdatedResponse {
  type: 'spec_updated'
  message: string
  spec_summary: SpecSummary
}

export type AssistantResponse = ProposalResponse | ResultResponse | ErrorResponse | SpecUpdatedResponse

export type RunStatus = 'queued' | 'running' | 'done' | 'failed'

export interface RunStatusResponse {
  status: RunStatus
  metrics?: Record<string, number | string>
  artifacts?: ArtifactRef[]
  error_message?: string
}
