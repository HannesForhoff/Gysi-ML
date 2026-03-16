import json
from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gysi_ml.api.schemas import ErrorResponse, MessageRequest, MessageResponse
from gysi_ml.config import get_settings
from gysi_ml.persistence import message_repository, session_repository
from gysi_ml.services.message_service import LLM_NOT_CONFIGURED, handle_message

router = APIRouter(prefix="/v1")


def _get_db_path(request: Request) -> str | None:
    return getattr(request.app.state, "db_path", None)


def _get_data_path(request: Request) -> str:
    return getattr(request.app.state, "data_path", get_settings().data_path)


def _get_artifacts_path(request: Request) -> str:
    return getattr(request.app.state, "artifacts_path", get_settings().artifacts_path)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"description": "LLM nicht konfiguriert"},
    },
)
def send_message(
    session_id: str,
    body: MessageRequest,
    request: Request,
) -> Union[MessageResponse, JSONResponse]:
    db_path = _get_db_path(request)

    # 1. Session validieren (404 / 409)
    session = session_repository.get_session(session_id=session_id, db_path=db_path)
    if session is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="session_not_found",
                detail=f"Session mit ID '{session_id}' nicht gefunden.",
                code="SESSION_NOT_FOUND",
            ).model_dump(),
        )
    if session["status"] == "closed":
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="session_closed",
                detail=f"Session '{session_id}' ist geschlossen.",
                code="SESSION_CLOSED",
            ).model_dump(),
        )

    # 2. User-Message speichern
    message_repository.save_message(
        session_id=session_id, role="user", content=body.text, db_path=db_path
    )

    # 3. An MessageService delegieren
    result = handle_message(
        session_id=session_id,
        text=body.text,
        db_path=db_path,
        data_path=_get_data_path(request),
        artifacts_path=_get_artifacts_path(request),
    )

    # 4. Assistenten-Antwort speichern
    message_repository.save_message(
        session_id=session_id,
        role="assistant",
        content=json.dumps(result, ensure_ascii=False),
        db_path=db_path,
    )

    # 5. Response
    if result.get("error_code") == LLM_NOT_CONFIGURED:
        return JSONResponse(status_code=503, content=result)
    if result.get("type") == "error":
        return JSONResponse(status_code=422, content=result)
    return MessageResponse(**result)
