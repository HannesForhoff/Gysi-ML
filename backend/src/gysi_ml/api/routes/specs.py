"""API-Endpunkte für Spec-Version-Abfragen."""
from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gysi_ml.api.schemas import ErrorResponse, SpecVersionResponse
from gysi_ml.persistence import spec_repository

router = APIRouter(prefix="/v1")


def _get_db_path(request: Request) -> str | None:
    return getattr(request.app.state, "db_path", None)


@router.get(
    "/sessions/{session_id}/spec",
    response_model=SpecVersionResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_latest_spec(
    session_id: str, request: Request
) -> Union[SpecVersionResponse, JSONResponse]:
    db_path = _get_db_path(request)
    row = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="spec_not_found",
                detail=f"Keine Spec für Session '{session_id}' vorhanden.",
                code="SPEC_NOT_FOUND",
            ).model_dump(),
        )
    return SpecVersionResponse(**row)


@router.get(
    "/sessions/{session_id}/spec/{version}",
    response_model=SpecVersionResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_spec_by_version(
    session_id: str, version: str, request: Request
) -> Union[SpecVersionResponse, JSONResponse]:
    db_path = _get_db_path(request)
    row = spec_repository.get_spec_by_version(
        session_id=session_id, version=version, db_path=db_path
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="spec_version_not_found",
                detail=f"Spec-Version '{version}' für Session '{session_id}' nicht gefunden.",
                code="SPEC_VERSION_NOT_FOUND",
            ).model_dump(),
        )
    return SpecVersionResponse(**row)
