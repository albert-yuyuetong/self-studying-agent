from fastapi import FastAPI

from app.api.v1.routes import router as v1_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(v1_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok", "env": settings.app_env}
