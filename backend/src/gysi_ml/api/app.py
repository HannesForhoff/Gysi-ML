from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import gysi_ml.steps  # noqa: F401 — registriert alle @register_step-Decorators beim Import
from gysi_ml.api.routes.artifacts import router as artifacts_router
from gysi_ml.api.routes.capabilities import router as capabilities_router
from gysi_ml.api.routes.confirm import router as confirm_router
from gysi_ml.api.routes.execute import router as execute_router
from gysi_ml.api.routes.health import router as health_router
from gysi_ml.api.routes.messages import router as messages_router
from gysi_ml.api.routes.rollback import router as rollback_router
from gysi_ml.api.routes.data import router as data_router
from gysi_ml.api.routes.runs import router as runs_router
from gysi_ml.api.routes.sessions import router as sessions_router
from gysi_ml.api.routes.specs import router as specs_router
from gysi_ml.api.schemas import ErrorResponse
from gysi_ml.config import Settings, get_settings
from gysi_ml.persistence.schema import create_all_tables


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        create_all_tables(settings.db_path)
        yield

    app = FastAPI(title="gysi-ml", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.db_path = settings.db_path
    app.state.data_path = settings.data_path
    app.state.artifacts_path = settings.artifacts_path
    app.state.openai_api_key = settings.openai_api_key
    app.state.llm_model = settings.llm_model

    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(confirm_router)
    app.include_router(execute_router)
    app.include_router(runs_router)
    app.include_router(data_router)   # DV-1.2
    app.include_router(specs_router)
    app.include_router(capabilities_router)
    app.include_router(artifacts_router)
    app.include_router(rollback_router)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="not_found",
                detail="Die angeforderte Ressource wurde nicht gefunden.",
                code="NOT_FOUND",
            ).model_dump(),
        )

    return app
