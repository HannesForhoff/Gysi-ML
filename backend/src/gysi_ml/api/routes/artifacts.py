import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from gysi_ml.api.schemas import ErrorResponse
from gysi_ml.persistence import artifact_repository

router = APIRouter(prefix="/v1", tags=["artifacts"])


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
    return FileResponse(file_path, media_type="image/png")
