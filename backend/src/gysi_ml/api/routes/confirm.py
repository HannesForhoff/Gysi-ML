import json
from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gysi_ml.api.schemas import ConfirmRequest, ErrorResponse, MessageResponse
from gysi_ml.config import get_settings
from gysi_ml.persistence import message_repository, session_repository
from gysi_ml.services.proposal_service import confirm_proposal

router = APIRouter(prefix="/v1")


def _get_db_path(request: Request) -> str | None:
    return getattr(request.app.state, "db_path", None)


def _get_data_path(request: Request) -> str:
    return getattr(request.app.state, "data_path", get_settings().data_path)


def _get_artifacts_path(request: Request) -> str:
    return getattr(request.app.state, "artifacts_path", get_settings().artifacts_path)


@router.post(
    "/sessions/{session_id}/confirm",
    response_model=MessageResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def confirm(
    session_id: str,
    body: ConfirmRequest,
    request: Request,
) -> Union[MessageResponse, JSONResponse]:
    db_path = _get_db_path(request)

    # 1. Session validieren
    session = session_repository.get_session(session_id=session_id, db_path=db_path)
    if session is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="session_not_found",
                detail=f"Session '{session_id}' nicht gefunden.",
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

    # 2. Proposal bestätigen + ausführen
    result = confirm_proposal(
        session_id=session_id,
        proposal_id=body.proposal_id,
        db_path=db_path,
        data_path=_get_data_path(request),
        artifacts_path=_get_artifacts_path(request),
    )

    # 3. Fehlerbehandlung
    if result.get("error") == "proposal_not_found":
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="proposal_not_found",
                detail=f"Proposal '{body.proposal_id}' nicht gefunden.",
                code="PROPOSAL_NOT_FOUND",
            ).model_dump(),
        )
    if result.get("error") == "no_pending_proposal":
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="no_pending_proposal",
                detail="Kein offener Vorschlag in dieser Session.",
                code="NO_PENDING_PROPOSAL",
            ).model_dump(),
        )

    # 4. Assistant-Message persistieren
    message_repository.save_message(
        session_id=session_id,
        role="assistant",
        content=json.dumps(result, ensure_ascii=False),
        db_path=db_path,
    )

    return MessageResponse(**result)
