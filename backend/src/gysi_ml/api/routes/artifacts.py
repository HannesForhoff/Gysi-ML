import mimetypes
import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from gysi_ml.api.schemas import ErrorResponse
from gysi_ml.persistence import artifact_repository

router = APIRouter(prefix="/v1", tags=["artifacts"])

# Mapping: DB-Artefakt-Typ → lesbarer Download-Dateiname.
# Entkoppelt den physischen Disk-Dateinamen (UUID-basiert) vom HTTP Content-Disposition Header.
# Bei unbekannten Typen greift der Fallback auf os.path.basename(file_path).
_TYPE_TO_DOWNLOAD_FILENAME: dict[str, str] = {
    "split_train": "trainingsdaten.csv",
    "split_test": "testdaten.csv",
    "feature_importance": "decision_tree_feature_importance.png",
    "ebm_global_explanation": "ebm_feature_importance.png",
    "correlation_filter_result": "correlation_filter_ergebnis.csv",
    "time_features_result": "time_features_ergebnis.csv",
}


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, request: Request):
    db_path = getattr(request.app.state, "db_path", None)
    artifacts_path = getattr(request.app.state, "artifacts_path", None)
    record = artifact_repository.get_artifact(artifact_id, db_path=db_path)
    if record is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="artifact_not_found",
                detail=f"Artefakt '{artifact_id}' nicht gefunden.",
                code="ARTIFACT_NOT_FOUND",
            ).model_dump(),
        )
    file_path = record["file_path"]
    # Path Traversal Protection: Pfad muss innerhalb von artifacts_path liegen
    if artifacts_path:
        real_file = os.path.realpath(file_path)
        real_base = os.path.realpath(artifacts_path)
        if not real_file.startswith(real_base + os.sep) and real_file != real_base:
            return JSONResponse(
                status_code=403,
                content=ErrorResponse(
                    error="access_denied",
                    detail="Zugriff auf diese Datei ist nicht erlaubt.",
                    code="ACCESS_DENIED",
                ).model_dump(),
            )
    if not os.path.isfile(file_path):
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="artifact_file_missing",
                detail="Artefakt-Datei nicht gefunden.",
                code="ARTIFACT_FILE_MISSING",
            ).model_dump(),
        )
    filename = _TYPE_TO_DOWNLOAD_FILENAME.get(
        record.get("type", ""), os.path.basename(file_path)
    )
    mime_type, _ = mimetypes.guess_type(file_path)
    media_type = mime_type or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type, filename=filename)
