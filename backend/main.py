from fastapi import FastAPI

from backend.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Self-Studying Agent",
        summary="家长端 AI 辅导助手最小工程骨架",
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()
