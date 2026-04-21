"""API-Endpunkte für Spec-Version-Abfragen."""
import json
from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gysi_ml.api.schemas import (
    ErrorResponse,
    SpecVersionResponse,
    VersionNodeResponse,
    VersionTreeResponse,
)
from gysi_ml.persistence import run_repository, session_repository, spec_repository

router = APIRouter(prefix="/v1")

_MODELING_STEPS = {"train_decision_tree", "train_ebm", "catboost_feature_selection"}


def _derive_phase(spec: dict) -> str:
    """Leitet die Phase aus der Spec ab: 'modeling' wenn ein aktivierter Modeling-Step vorhanden ist."""
    for step in spec.get("steps", []):
        if step.get("enabled", True) and step.get("type") in _MODELING_STEPS:
            return "modeling"
    return "preprocessing"


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
    "/sessions/{session_id}/spec/tree",
    response_model=VersionTreeResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_spec_tree(
    session_id: str, request: Request
) -> Union[VersionTreeResponse, JSONResponse]:
    db_path = _get_db_path(request)

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

    specs = spec_repository.get_all_specs_for_session(session_id=session_id, db_path=db_path)

    runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
    runs_by_spec: dict[str, list] = {}
    for run in runs:
        spec_id = run.get("spec_id")
        if spec_id:
            runs_by_spec.setdefault(spec_id, []).append(run)

    active_spec_id = specs[-1]["spec_id"] if specs else None

    nodes = []
    for spec in specs:
        spec_dict = json.loads(spec["spec_json"]) if spec.get("spec_json") else {}
        phase = _derive_phase(spec_dict)
        spec_runs = runs_by_spec.get(spec["spec_id"], [])
        last_run = spec_runs[-1] if spec_runs else None
        nodes.append(
            VersionNodeResponse(
                spec_id=spec["spec_id"],
                version=spec["version"],
                parent_spec_id=spec.get("parent_spec_id"),
                change_summary=spec.get("change_summary"),
                created_at=spec["created_at"],
                has_runs=len(spec_runs) > 0,
                last_run_status=last_run["status"] if last_run else None,
                last_run_id=last_run["run_id"] if last_run else None,
                phase=phase,
            )
        )

    return VersionTreeResponse(
        session_id=session_id,
        active_spec_id=active_spec_id,
        versions=nodes,
    )


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
