"""Durable job queue with idempotency and bounded retries."""

import json
import sqlite3
from pathlib import Path

from .db import connect, json_dump

TERMINAL = {"succeeded", "failed", "needs_approval", "cancelled"}


def serialize(row):
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    raw = item.pop("result_json")
    item["result"] = json.loads(raw) if raw else None
    return item


def enqueue(path: Path, kind: str, payload=None, idempotency_key=None, max_attempts=3):
    if not kind or len(kind) > 100:
        raise ValueError("kind must be 1-100 characters")
    if not 1 <= int(max_attempts) <= 10:
        raise ValueError("max_attempts must be between 1 and 10")
    with connect(path) as conn:
        if idempotency_key:
            old = conn.execute("SELECT * FROM jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if old:
                return serialize(old)
        cur = conn.execute(
            "INSERT INTO jobs(kind,payload_json,idempotency_key,max_attempts) VALUES(?,?,?,?)",
            (kind, json_dump(payload or {}), idempotency_key, max_attempts),
        )
        job_id = cur.lastrowid
        conn.execute(
            "INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("job.queued", "job", str(job_id), json_dump({"kind": kind})),
        )
        return serialize(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def list_jobs(path: Path, limit=50):
    limit = max(1, min(int(limit), 200))
    with connect(path) as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [serialize(row) for row in rows]


def claim_next(path: Path):
    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if row is None:
            conn.commit()
            return None
        conn.execute(
            "UPDATE jobs SET status='running',attempts=attempts+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='queued'",
            (row["id"],),
        )
        conn.execute(
            "INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("job.started", "job", str(row["id"]), "{}"),
        )
        updated = conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        conn.commit()
        return serialize(updated)


def finish(path: Path, job_id: int, result=None):
    _transition(path, job_id, "succeeded", result or {})


def fail(path: Path, job_id: int, error: str, retry=True):
    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or row["status"] != "running":
            raise ValueError("only a running job can fail")
        status = "queued" if retry and row["attempts"] < row["max_attempts"] else "failed"
        conn.execute(
            "UPDATE jobs SET status=?,error=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
            (status, str(error)[:2000], job_id),
        )
        conn.execute(
            "INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("job.retry" if status == "queued" else "job.failed", "job", str(job_id),
             json_dump({"error": str(error)[:500], "next_status": status})),
        )
        conn.commit()


def _transition(path: Path, job_id: int, status: str, result):
    if status not in TERMINAL:
        raise ValueError("invalid terminal state")
    with connect(path) as conn:
        cur = conn.execute(
            "UPDATE jobs SET status=?,result_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='running'",
            (status, json_dump(result), job_id),
        )
        if cur.rowcount != 1:
            raise ValueError("only a running job can transition")
        conn.execute(
            "INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("job." + status, "job", str(job_id), json_dump(result)),
        )
