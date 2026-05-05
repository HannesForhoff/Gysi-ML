"""API-Endpunkte: Datensatz-Zugriff auf Run-Snapshot (Story DV-1.2, DV-1.3)."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Union

import pandas as pd
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gysi_ml.api.schemas import DataPageResponse, ErrorResponse
from gysi_ml.config import get_settings
from gysi_ml.persistence import run_repository
from gysi_ml.services.snapshot_service import _compute_column_stats
from gysi_ml.utils.data_loader import load_bikes_dataset

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
    df = load_bikes_dataset(str(csv_path))
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
    split_filter: str = Query("all", pattern="^(all|train|test)$"),
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

    # Parquet laden
    df = pd.read_parquet(parquet_path)

    # is_split, train_rows, test_rows aus vorberechneter JSON lesen
    is_split = False
    train_rows: int | None = None
    test_rows: int | None = None
    stats_data: dict = {}
    stats_path = Path(artifacts_path) / f"{run_id}_column_stats.json"
    if stats_path.exists():
        stats_data = json.loads(stats_path.read_text(encoding="utf-8"))
        is_split = bool(stats_data.get("is_split", False))
        train_rows = stats_data.get("train_rows")
        test_rows = stats_data.get("test_rows")

    # Split-Filter anwenden (nur wenn _split-Spalte vorhanden)
    if split_filter in ("train", "test") and "_split" in df.columns:
        df = df[df["_split"] == split_filter].reset_index(drop=True)

    # _split-Spalte aus Antwort ausschließen
    visible_cols = [c for c in df.columns if c != "_split"]
    df_view = df[visible_cols]

    total_rows = len(df_view)
    page = df_view.iloc[offset : offset + effective_limit]

    # NaN → None damit JSON valide bleibt
    page = page.where(page.notna(), other=None)

    columns = list(df_view.columns)
    rows = [list(row) for row in page.itertuples(index=False, name=None)]

    # Column-Stats: bei gefilterter Ansicht dynamisch aus der gefilterten Partition berechnen,
    # damit Histogramme/min/max die tatsächliche Teilmenge widerspiegeln (nur bei offset==0)
    column_stats: dict | None = None
    if offset == 0:
        if split_filter in ("train", "test"):
            computed = _compute_column_stats(df_view, is_split=False)
            column_stats = computed.get("columns")
        elif stats_path.exists():
            column_stats = stats_data.get("columns")

    return DataPageResponse(
        columns=columns,
        rows=rows,
        total_rows=total_rows,
        train_rows=train_rows,
        test_rows=test_rows,
        offset=offset,
        limit=effective_limit,
        is_split=is_split,
        column_stats=column_stats,
    )


@router.get(
    "/sessions/{session_id}/raw-data/download",
    response_model=None,
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV-Download des Rohdatensatzes"},
        404: {"model": ErrorResponse},
    },
)
def download_raw_data_csv(
    session_id: str,
    request: Request,
) -> Union[StreamingResponse, JSONResponse]:
    """Streamt den Rohdatensatz (bikes.csv) als CSV-Datei.

    Content-Disposition: attachment; filename="gysi_raw_data.csv"
    Hinweis: session_id wird nicht validiert — bikes.csv ist ein globaler
    Datensatz ohne Session-Zugehörigkeit (Single-User-System).
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

    df = load_bikes_dataset(str(csv_path))
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.read()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gysi_raw_data.csv"'},
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

    Content-Disposition: attachment; filename="bikes_{spec_version}.csv"
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

    spec_version = row.get("spec_version") or run_id[:8]
    safe_version = re.sub(r'[^a-zA-Z0-9._\-]', '_', str(spec_version))
    filename = f"bikes_{safe_version}.csv"
    return StreamingResponse(
        iter([buffer.read()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
