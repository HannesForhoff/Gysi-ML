from fastapi import APIRouter

from gysi_ml.api.schemas import HealthResponse
from gysi_ml.config import get_settings

router = APIRouter()


@router.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        llm_model=settings.llm_model or None,
    )
