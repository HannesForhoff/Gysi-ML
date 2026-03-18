from datetime import datetime
from typing import Any, Optional

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


class MessageResponse(BaseModel):
    """Typisierte Response fuer POST /messages."""

    type: str  # "proposal" | "result" | "error" | "spec_updated" | "comparison"
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
