from typing import Optional, Union

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from gysi_ml.api.schemas import (
    ErrorResponse,
    MessageSummary,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
)
from gysi_ml.persistence import message_repository, session_repository, spec_repository

router = APIRouter(prefix="/v1")


def _get_db_path(request: Request) -> str | None:
    return getattr(request.app.state, "db_path", None)


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    request: Request,
    body: Optional[SessionCreateRequest] = Body(default=None),
) -> SessionResponse:
    db_path = _get_db_path(request)
    name = body.name if body else None
    row = session_repository.create_session(name=name, db_path=db_path)
    # Basisknoten anlegen: repräsentiert den Rohdaten-Zustand vor jeder Transformation.
    # Dadurch ist im Versionsbaum immer ein Ausgangspunkt sichtbar.
    spec_repository.create_spec_version(
        session_id=row["session_id"], spec={"steps": []}, db_path=db_path
    )
    return SessionResponse(**row)


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(request: Request) -> SessionListResponse:
    db_path = _get_db_path(request)
    rows = session_repository.list_sessions(db_path=db_path)
    return SessionListResponse(sessions=[SessionResponse(**r) for r in rows])


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_session(session_id: str, request: Request) -> Union[SessionResponse, JSONResponse]:
    db_path = _get_db_path(request)
    row = session_repository.get_session(session_id=session_id, db_path=db_path)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="session_not_found",
                detail=f"Session mit ID '{session_id}' nicht gefunden.",
                code="SESSION_NOT_FOUND",
            ).model_dump(),
        )
    messages = message_repository.get_messages_for_session(
        session_id=session_id, db_path=db_path
    )
    return SessionResponse(**row, messages=[MessageSummary(**m) for m in messages])


@router.delete(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}},
)
def close_session(session_id: str, request: Request) -> Union[SessionResponse, JSONResponse]:
    db_path = _get_db_path(request)
    row = session_repository.close_session(session_id=session_id, db_path=db_path)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="session_not_found",
                detail=f"Session mit ID '{session_id}' nicht gefunden.",
                code="SESSION_NOT_FOUND",
            ).model_dump(),
        )
    return SessionResponse(**row)
