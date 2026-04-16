"""API-Endpunkte: Datensatz-Zugriff auf Run-Snapshot (Story DV-1.2, DV-1.3)."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Union

import pandas as pd
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gysi_ml.api.schemas import DataPageResponse, ErrorResponse
from gysi_ml.config import get_settings
from gysi_ml.persistence import run_repository
from gysi_ml.services.snapshot_service import _compute_column_stats

router = APIRouter(prefix="/v1")

_MAX_LIMIT = 1000


def _get_db_path(request: Request) -> str | None:
    return getattr(request.app.state, "db_path", None)


def _get_artifacts_path(request: Request) -> str:
    return getattr(request.app.state, "artifacts_path", get_settings().artifacts_path)


def _get_data_path(request: Request) -> str:
    return getattr(request.app.state, "data_path", get_settings().data_path)


@router.get(
    "/sessions/{session_id}/raw-data",
    response_model=DataPageResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_raw_data(
    session_id: str,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
) -> Union[DataPageResponse, JSONResponse]:
    """Gibt eine paginierte Seite des Rohdatensatzes (bikes.csv) zurück.

    Inkl. Column-Stats bei offset==0. Kein Run erforderlich.
    """
    data_path = _get_data_path(request)
    csv_path = Path(data_path)
    if not csv_path.exists():
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="raw_data_not_found",
                detail="Rohdatensatz nicht gefunden.",
                code="RAW_DATA_NOT_FOUND",
            ).model_dump(),
        )

    effective_limit = min(limit, _MAX_LIMIT)
    df = pd.read_csv(csv_path)
    total_rows = len(df)
    page = df.iloc[offset : offset + effective_limit]
    page = page.where(page.notna(), other=None)

    columns = list(df.columns)
    rows = [list(row) for row in page.itertuples(index=False, name=None)]

    column_stats: dict | None = None
    if offset == 0:
        stats_data = _compute_column_stats(df, is_split=False)
        column_stats = stats_data.get("columns")

    return DataPageResponse(
        columns=columns,
        rows=rows,
        total_rows=total_rows,
        offset=offset,
        limit=effective_limit,
        is_split=False,
        column_stats=column_stats,
    )


@router.get(
    "/sessions/{session_id}/runs/{run_id}/data",
    response_model=DataPageResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_run_data(
    session_id: str,
    run_id: str,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
) -> Union[DataPageResponse, JSONResponse]:
    """Gibt eine paginierte Seite des Run-Snapshots zurück.

    column_stats wird nur bei offset==0 mitgeliefert.
    limit wird serverseitig auf 1000 geclampt.
    """
    db_path = _get_db_path(request)
    artifacts_path = _get_artifacts_path(request)

    # Session-Zugehörigkeit des Runs prüfen
    row = run_repository.get_run(run_id=run_id, db_path=db_path)
    if row is None or row.get("session_id") != session_id:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="run_not_found",
                detail=f"Run mit ID '{run_id}' nicht gefunden oder gehört nicht zu Session '{session_id}'.",
                code="RUN_NOT_FOUND",
            ).model_dump(),
        )

    # Snapshot-Datei prüfen
    parquet_path = Path(artifacts_path) / f"{run_id}_snapshot.parquet"
    if not parquet_path.exists():
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="snapshot_not_found",
                detail=f"Kein Snapshot für Run '{run_id}' vorhanden. Run wurde möglicherweise noch nicht erfolgreich abgeschlossen.",
                code="SNAPSHOT_NOT_FOUND",
            ).model_dump(),
        )

    # limit clampen
    effective_limit = min(limit, _MAX_LIMIT)

    # Parquet laden und paginieren
    df = pd.read_parquet(parquet_path)
    total_rows = len(df)
    page = df.iloc[offset : offset + effective_limit]

    # NaN → None damit JSON valide bleibt
    page = page.where(page.notna(), other=None)

    columns = list(df.columns)
    rows = [list(row) for row in page.itertuples(index=False, name=None)]

    # Column-Stats und is_split aus JSON lesen
    column_stats: dict | None = None
    is_split = False
    stats_path = Path(artifacts_path) / f"{run_id}_column_stats.json"
    if stats_path.exists():
        stats_data = json.loads(stats_path.read_text(encoding="utf-8"))
        is_split = bool(stats_data.get("is_split", False))
        if offset == 0:
            column_stats = stats_data.get("columns")

    return DataPageResponse(
        columns=columns,
        rows=rows,
        total_rows=total_rows,
        offset=offset,
        limit=effective_limit,
        is_split=is_split,
        column_stats=column_stats,
    )


@router.get(
    "/sessions/{session_id}/runs/{run_id}/data/download",
    response_model=None,
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV-Download des Run-Snapshots"},
        404: {"model": ErrorResponse},
    },
)
def download_run_data_csv(
    session_id: str,
    run_id: str,
    request: Request,
) -> Union[StreamingResponse, JSONResponse]:
    """Streamt den Run-Snapshot als CSV-Datei.

    Content-Disposition: attachment; filename="gysi_data_{run_id[:8]}.csv"
    Session-Zugehörigkeit wird geprüft.
    """
    db_path = _get_db_path(request)
    artifacts_path = _get_artifacts_path(request)

    # Session-Zugehörigkeit des Runs prüfen
    row = run_repository.get_run(run_id=run_id, db_path=db_path)
    if row is None or row.get("session_id") != session_id:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="run_not_found",
                detail=f"Run mit ID '{run_id}' nicht gefunden oder gehört nicht zu Session '{session_id}'.",
                code="RUN_NOT_FOUND",
            ).model_dump(),
        )

    # Snapshot-Datei prüfen
    parquet_path = Path(artifacts_path) / f"{run_id}_snapshot.parquet"
    if not parquet_path.exists():
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="snapshot_not_found",
                detail=f"Kein Snapshot für Run '{run_id}' vorhanden. Run wurde möglicherweise noch nicht erfolgreich abgeschlossen.",
                code="SNAPSHOT_NOT_FOUND",
            ).model_dump(),
        )

    # Parquet laden und als CSV streamen
    df = pd.read_parquet(parquet_path)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    filename = f"gysi_data_{run_id[:8]}.csv"
    return StreamingResponse(
        iter([buffer.read()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
