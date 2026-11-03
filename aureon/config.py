"""Dependency-free runtime configuration."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8787
    mode: str = "mock"
    data_dir: Path = Path("data")
    db_path: Path = Path("data/aureon.sqlite3")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls):
        data_dir = Path(os.getenv("AUREON_DATA_DIR", "data")).expanduser()
        db_path = Path(os.getenv("AUREON_DB_PATH", str(data_dir / "aureon.sqlite3"))).expanduser()
        mode = os.getenv("AUREON_MODE", "mock").strip().lower()
        if mode not in {"mock", "live"}:
            raise ValueError("AUREON_MODE must be mock or live")
        port = int(os.getenv("AUREON_PORT", "8787"))
        if not 1 <= port <= 65535:
            raise ValueError("AUREON_PORT must be between 1 and 65535")
        return cls(
            host=os.getenv("AUREON_HOST", "127.0.0.1"),
            port=port,
            mode=mode,
            data_dir=data_dir,
            db_path=db_path,
            log_level=os.getenv("AUREON_LOG_LEVEL", "INFO").upper(),
        )
