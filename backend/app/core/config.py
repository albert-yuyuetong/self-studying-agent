from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
# Keep explicit process environment authoritative. Resolve .env independently of cwd.
load_dotenv(BACKEND_DIR / ".env", override=False)


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "true" if default else "false").strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true or false")
    return value in {"true", "1", "yes"}


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "self-studying-agent"))
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    app_host: str = field(default_factory=lambda: os.getenv("APP_HOST", "127.0.0.1"))
    app_port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    cors_allow_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOW_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
            ).split(",")
            if origin.strip()
        )
    )
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", str(BACKEND_DIR / "data" / "tutor.sqlite3"))
    )
    llm_enabled: bool = field(default_factory=lambda: _boolean("LLM_ENABLED"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""), repr=False)
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    # Model names and capabilities are chosen by the operator; do not silently assume one.
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    llm_verify_model: str = field(default_factory=lambda: os.getenv("LLM_VERIFY_MODEL", ""))
    llm_vision_enabled: bool = field(default_factory=lambda: _boolean("LLM_VISION_ENABLED"))
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "90")))

    def __post_init__(self) -> None:
        if not 1 <= self.app_port <= 65535:
            raise ValueError("APP_PORT must be between 1 and 65535")
        if not 1 <= self.llm_timeout_seconds <= 600:
            raise ValueError("LLM_TIMEOUT_SECONDS must be between 1 and 600")
        # Validate configuration without including sensitive supplied values in error messages.
        try:
            address = urlsplit(self.llm_base_url)
            port = address.port
        except ValueError:
            raise ValueError("LLM_BASE_URL must contain a valid service address and port") from None
        if address.scheme not in {"http", "https"} or not address.netloc:
            raise ValueError("LLM_BASE_URL must be an HTTP or HTTPS service root")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("LLM_BASE_URL port must be between 1 and 65535")
        if address.username or address.password or address.query or address.fragment:
            raise ValueError("LLM_BASE_URL must not contain credentials, query parameters or fragments")
        if not self.database_path.strip():
            raise ValueError("DATABASE_PATH cannot be empty")


settings = Settings()
