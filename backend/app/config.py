"""Runtime configuration.

Every path is resolved from this file so the app can be started from any
working directory (uvicorn, pytest, a notebook, or the CLI).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    backend_dir: Path
    data_dir: Path
    knowledge_dir: Path
    cache_dir: Path
    frontend_dir: Path
    user_agent: str = "Domino-Agent research domino-agent@example.com"
    request_timeout: float = 30.0
    max_retries: int = 3
    min_request_interval: float = 0.12
    cors_origins: tuple[str, ...] = field(
        default=("http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000")
    )

    @property
    def events_path(self) -> Path:
        return self.data_dir / "events" / "events.yaml"

    @property
    def mechanisms_path(self) -> Path:
        return self.knowledge_dir / "mechanisms.yaml"

    @property
    def prices_path(self) -> Path:
        return self.data_dir / "market" / "prices.csv"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    backend_dir = Path(__file__).resolve().parents[1]
    root_dir = backend_dir.parent
    data_dir = Path(os.getenv("DOMINO_DATA_DIR", backend_dir / "data")).resolve()
    cache_dir = Path(
        os.getenv("DOMINO_CACHE_DIR", backend_dir / ".cache")
    ).resolve()
    origins = os.getenv("DOMINO_CORS_ORIGINS", "")
    cors = tuple(o.strip() for o in origins.split(",") if o.strip()) or (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    )
    return Settings(
        root_dir=root_dir,
        backend_dir=backend_dir,
        data_dir=data_dir,
        knowledge_dir=data_dir / "knowledge",
        cache_dir=cache_dir,
        frontend_dir=root_dir / "frontend",
        user_agent=os.getenv("DOMINO_USER_AGENT", Settings.user_agent),
        cors_origins=cors,
    )


def ensure_cache_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    return settings.cache_dir
