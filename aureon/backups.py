"""Verified local SQLite backups with bounded retention."""
import os
import sqlite3
import shutil
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def _check(path):
    with closing(sqlite3.connect(str(path))) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not result or result[0] != "ok":
        raise RuntimeError("SQLite integrity check failed: " + str(path))
    if not {"workspace_records", "jobs", "events"}.issubset(tables):
        raise ValueError("file is not a valid Aureon database backup")


def list_backups(db_path, backup_dir=None):
    source = Path(db_path)
    folder = Path(backup_dir) if backup_dir else source.parent / "backups"
    if not folder.exists():
        return []
    return [{"path": str(p), "name": p.name, "size_bytes": p.stat().st_size,
             "modified_at": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()}
            for p in sorted(folder.glob("aureon-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)]


def backup_database(db_path, backup_dir=None, retain=7):
    source = Path(db_path)
    if not source.is_file():
        raise ValueError("database file does not exist")
    if isinstance(retain, bool) or not isinstance(retain, int) or not 1 <= retain <= 50:
        raise ValueError("retain must be between 1 and 50")
    folder = Path(backup_dir) if backup_dir else source.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    target = folder / ("aureon-" + stamp + ".sqlite3")
    temp = target.with_suffix(".tmp")
    try:
        with closing(sqlite3.connect(str(source), timeout=20)) as src, closing(sqlite3.connect(str(temp))) as dst:
            src.backup(dst)
            dst.commit()
        _check(temp)
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    backups = list_backups(source, folder)
    for item in backups[retain:]:
        Path(item["path"]).unlink(missing_ok=True)
    return {"path": str(target), "size_bytes": target.stat().st_size,
            "integrity": "ok", "retained": min(len(backups), retain)}


def backup_if_due(db_path, backup_dir=None, interval_hours=24):
    if isinstance(interval_hours, bool) or not isinstance(interval_hours, (int, float)) or not 1 <= interval_hours <= 720:
        raise ValueError("interval_hours must be between 1 and 720")
    backups = list_backups(db_path, backup_dir)
    if backups:
        latest = datetime.fromisoformat(backups[0]["modified_at"])
        age = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
        if age < interval_hours:
            return {"created": False, "latest": backups[0], "reason": "backup is still recent"}
    return {"created": True, **backup_database(db_path, backup_dir)}


def restore_backup(db_path, backup_path, backup_dir=None):
    target = Path(db_path)
    source = Path(backup_path)
    if not source.is_file() or target.resolve() == source.resolve():
        raise ValueError("a different existing backup file is required")
    _check(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Keep the selected backup safe while the pre-restore backup enforces
    # retention; otherwise retention could delete the very file being restored.
    protected_fd, protected_name = tempfile.mkstemp(
        prefix=".aureon-restore-source-", suffix=".sqlite3", dir=str(target.parent))
    os.close(protected_fd)
    protected = Path(protected_name)
    restore_fd, restore_name = tempfile.mkstemp(
        prefix=".aureon-restore-target-", suffix=".sqlite3", dir=str(target.parent))
    os.close(restore_fd)
    temp = Path(restore_name)
    safety = None
    try:
        shutil.copy2(source, protected)
        safety = backup_database(target, backup_dir) if target.exists() else None
        with closing(sqlite3.connect(str(protected))) as src, closing(sqlite3.connect(str(temp))) as dst:
            src.backup(dst)
            dst.commit()
        _check(temp)
        os.replace(temp, target)
    finally:
        protected.unlink(missing_ok=True)
        temp.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(target) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    return {"restored_from": str(source), "integrity": "ok", "pre_restore_backup": safety}
