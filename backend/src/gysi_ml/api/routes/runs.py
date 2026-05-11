"""API-Endpunkte für Run-Abfragen."""
from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gysi_ml.api.schemas import (
    ErrorResponse,
    RunDetailResponse,
    RunListResponse,
    RunSummaryResponse,
)
from gysi_ml.persistence import run_repository
from gysi_ml.services.message_service import _get_suggested_next_steps

router = APIRouter(prefix="/v1")


def _get_db_path(request: Request) -> str | None:
    return getattr(request.app.state, "db_path", None)


@router.get("/sessions/{session_id}/runs", response_model=RunListResponse)
def list_runs(session_id: str, request: Request) -> RunListResponse:
    db_path = _get_db_path(request)
    rows = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
    return RunListResponse(runs=[RunSummaryResponse(**r) for r in rows])


@router.get(
    "/sessions/{session_id}/runs/{run_id}",
    response_model=RunDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_run(
    session_id: str, run_id: str, request: Request
) -> Union[RunDetailResponse, JSONResponse]:
    db_path = _get_db_path(request)
    row = run_repository.get_run(run_id=run_id, db_path=db_path)
    if row is None or row.get("session_id") != session_id:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="run_not_found",
                detail=f"Run mit ID '{run_id}' nicht gefunden.",
                code="RUN_NOT_FOUND",
            ).model_dump(),
        )
    result = row.get("result") or {}
    spec = row.get("spec")
    return RunDetailResponse(
        run_id=row["run_id"],
        status=row["status"],
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        spec_version=row.get("spec_version"),
        spec=spec,
        step_results=result.get("step_results"),
        metrics=result.get("metrics"),
        artifacts=result.get("artifacts"),
        error_message=row.get("error_message"),
        suggested_next_steps=_get_suggested_next_steps(spec) if row["status"] == "done" else None,
    )
