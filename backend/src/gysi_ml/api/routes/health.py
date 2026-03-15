from fastapi import APIRouter

from gysi_ml.api.schemas import HealthResponse

router = APIRouter()


@router.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
