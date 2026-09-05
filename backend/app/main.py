from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router
from app.core.config import settings
from app.orchestration.tutor_orchestrator import TutorOrchestrator
from app.repositories.profile_repository import (
    RepositoryConflict, RepositoryNotFound, SQLiteTutorRepository,
)
from app.services.tutor_engine import TutorEngine


def create_app(
    repo: SQLiteTutorRepository | None = None, engine: TutorEngine | None = None,
) -> FastAPI:
    application = FastAPI(title=settings.app_name, version="0.2.0")
    application.state.tutor = TutorOrchestrator(
        repo if repo is not None else SQLiteTutorRepository(settings.database_path),
        engine=engine,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(RepositoryConflict)
    async def conflict(_request: Request, exc: RepositoryConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(RepositoryNotFound)
    async def not_found(_request: Request, exc: RepositoryNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.app_name, "status": "ok", "env": settings.app_env}

    application.include_router(router, prefix="/api/v1")
    return application


app = create_app()

