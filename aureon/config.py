"""Dependency-free runtime configuration."""
import os
from dataclasses import dataclass
from pathlib import Path


def _load_local_env(path=Path(".env")):
    """Load simple KEY=VALUE entries without shell execution or overriding exports."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key.startswith("AUREON_") and key.replace("_", "").isalnum() and key not in os.environ:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\\\"", "\'"}:
                value = value[1:-1]
            os.environ[key] = value

@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8787
    mode: str = "local"
    data_dir: Path = Path("data")
    db_path: Path = Path("data/aureon.sqlite3")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls):
        _load_local_env()
        data_dir = Path(os.getenv("AUREON_DATA_DIR", "data")).expanduser()
        db_path = Path(os.getenv("AUREON_DB_PATH", str(data_dir / "aureon.sqlite3"))).expanduser()
        # The application always runs locally; individual providers report their own live status.
        mode = "local"
        port = int(os.getenv("AUREON_PORT", "8787"))
        if not 1 <= port <= 65535:
            raise ValueError("AUREON_PORT must be between 1 and 65535")
        host = os.getenv("AUREON_HOST", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("AUREON_HOST must be localhost until remote access is secured")
        return cls(host=host, port=port, mode=mode, data_dir=data_dir, db_path=db_path,
                   log_level=os.getenv("AUREON_LOG_LEVEL", "INFO").upper())
