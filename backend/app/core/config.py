from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "self-studying-agent")
    app_env: str = os.getenv("APP_ENV", "dev")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    cors_allow_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOW_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    )
    llm_enabled: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))


settings = Settings()
