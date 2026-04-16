from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = None


class MessageSummary(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    name: Optional[str]
    created_at: datetime
    status: str
    messages: Optional[list["MessageSummary"]] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    code: str


class HealthResponse(BaseModel):
    status: str
    llm_model: str | None = None


class ExecuteRequest(BaseModel):
    spec: dict


class ExecuteResponse(BaseModel):
    run_id: str
    status: str
    result: Any


class RunSummaryResponse(BaseModel):
    run_id: str
    status: str
    started_at: Optional[str] = None
    spec_version: Optional[str] = None


class ArtifactSummary(BaseModel):
    artifact_id: str
    type: str
    created_at: str


class RunDetailResponse(BaseModel):
    run_id: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    spec_version: Optional[str] = None
    spec: Optional[dict] = None
    step_results: Optional[list] = None
    metrics: Optional[dict] = None
    artifacts: Optional[list[ArtifactSummary]] = None
    error_message: Optional[str] = None


class DataPageResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    total_rows: int
    offset: int
    limit: int
    is_split: bool
    column_stats: Optional[dict] = None  # nur bei offset == 0 befüllt


class RunListResponse(BaseModel):
    runs: list[RunSummaryResponse]


class StepCapability(BaseModel):
    type: str
    description: str
    params: dict


class CapabilitiesResponse(BaseModel):
    steps: list[StepCapability]


class SpecVersionResponse(BaseModel):
    spec_id: str
    session_id: str
    version: str
    spec: dict
    created_at: str


class MessageRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(..., min_length=1)


class ConfirmRequest(BaseModel):
    proposal_id: str
    confirmed_steps: Optional[list[int]] = None  # None = alle Steps ausführen
    mode: Literal["all", "step_by_step"] = "all"


class CompletedStepSchema(BaseModel):
    type: str
    summary: str
    metadata: Optional[dict] = None


class MessageResponse(BaseModel):
    """Typisierte Response fuer POST /messages."""

    type: str  # "proposal" | "result" | "error" | "spec_updated" | "info" | "comparison" | "step_result"
    run_id: Optional[str] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    steps: Optional[list[dict]] = None
    explanation: Optional[str] = None
    confirmation_required: Optional[bool] = None
    proposal_id: Optional[str] = None
    spec_id: Optional[str] = None
    version: Optional[str] = None
    spec: Optional[dict] = None
    runs: Optional[list[dict]] = None
    better_run_id: Optional[str] = None
    step_results: Optional[list] = None
    artifacts: Optional[list] = None
    # Step-by-Step-Felder (Story 9.3)
    completed_step: Optional[CompletedStepSchema] = None
    remaining_steps: Optional[list[dict]] = None
    next_action: Optional[str] = None
    state_id: Optional[str] = None
    is_final: Optional[bool] = None
    completed_steps_summary: Optional[list[CompletedStepSchema]] = None


class VersionNodeResponse(BaseModel):
    spec_id: str
    version: str
    parent_spec_id: Optional[str] = None
    change_summary: Optional[str] = None
    created_at: str
    has_runs: bool
    last_run_status: Optional[str] = None


class VersionTreeResponse(BaseModel):
    session_id: str
    active_spec_id: Optional[str] = None
    versions: list[VersionNodeResponse]
