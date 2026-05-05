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
  data_leakage_warning?: boolean
  leakage_steps?: string[]
}

export interface StepResult {
  step_type: string
  metadata: Record<string, unknown>
}

export interface ResultResponse {
  type: 'result'
  message: string
  status: 'done' | 'failed'
  run_id?: string
  post_run_explanation?: string
  metrics?: Record<string, number | string>
  artifacts?: ArtifactRef[]
  spec_summary?: SpecSummary
  step_results?: StepResult[]
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

export interface InfoResponse {
  type: 'info'
  message: string
}

export type AssistantResponse = ProposalResponse | ResultResponse | ErrorResponse | SpecUpdatedResponse | InfoResponse

export interface VersionNode {
  spec_id: string
  version: string
  parent_spec_id: string | null
  change_summary: string | null
  created_at: string
  has_runs: boolean
  last_run_status: string | null
  last_run_id: string | null
  phase: string
}

export interface VersionTree {
  session_id: string
  active_spec_id: string | null
  versions: VersionNode[]
}

export type RunStatus = 'queued' | 'running' | 'done' | 'failed'

export interface RunStatusResponse {
  status: RunStatus
  metrics?: Record<string, number | string>
  artifacts?: ArtifactRef[]
  error_message?: string
  step_results?: StepResult[]
}
