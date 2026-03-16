"""API-Route: GET /v1/capabilities (Story 1.6)."""
from fastapi import APIRouter

from gysi_ml.api.schemas import CapabilitiesResponse
from gysi_ml.core.capabilities import get_capabilities

router = APIRouter(prefix="/v1")


@router.get("/capabilities", response_model=CapabilitiesResponse)
def list_capabilities() -> dict:
    """Gibt alle verfügbaren Pipeline-Steps mit Metadaten zurück."""
    return get_capabilities()
