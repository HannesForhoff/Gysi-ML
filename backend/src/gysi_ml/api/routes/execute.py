from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gysi_ml.api.schemas import ErrorResponse, ExecuteRequest, ExecuteResponse
from gysi_ml.config import get_settings
from gysi_ml.executor.executor import PipelineExecutor
from gysi_ml.persistence import session_repository

router = APIRouter(prefix="/v1")


def _get_db_path(request: Request) -> str | None:
    return getattr(request.app.state, "db_path", None)


def _get_data_path(request: Request) -> str:
    return getattr(request.app.state, "data_path", get_settings().data_path)


def _get_artifacts_path(request: Request) -> str:
    return getattr(request.app.state, "artifacts_path", get_settings().artifacts_path)


@router.post(
    "/sessions/{session_id}/execute",
    response_model=ExecuteResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"description": "Spec ungültig"},
    },
)
def execute_pipeline(
    session_id: str,
    body: ExecuteRequest,
    request: Request,
) -> Union[ExecuteResponse, JSONResponse]:
    db_path = _get_db_path(request)
    data_path = _get_data_path(request)
    artifacts_path = _get_artifacts_path(request)

    # 404: Session existiert nicht
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

    # 409: Session geschlossen
    if session["status"] == "closed":
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="session_closed",
                detail=f"Session '{session_id}' ist geschlossen und kann nicht ausgeführt werden.",
                code="SESSION_CLOSED",
            ).model_dump(),
        )

    executor = PipelineExecutor(data_path=data_path, artifacts_path=artifacts_path)
    result = executor.execute(spec=body.spec, session_id=session_id, db_path=db_path)

    if "error" in result:
        status_code = 422
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                error=result["error"],
                detail=result.get("detail", ""),
                code=result.get("code", "EXECUTION_ERROR"),
            ).model_dump(),
        )

    return ExecuteResponse(
        run_id=result["run_id"],
        status=result["status"],
        result=result["result"],
    )
