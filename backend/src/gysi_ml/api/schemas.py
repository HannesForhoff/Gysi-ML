from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    name: Optional[str]
    created_at: datetime
    status: str


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
