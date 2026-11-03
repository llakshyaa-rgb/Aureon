"""Persistent local scheduler; due work is enqueued, never auto-executed."""
import json
from datetime import datetime, timezone
from .db import connect, json_dump
from .jobs import enqueue
SCHEMA="""CREATE TABLE IF NOT EXISTS scheduled_jobs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
 run_at TEXT NOT NULL, idempotency_key TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'scheduled',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), enqueued_job_id INTEGER
); CREATE INDEX IF NOT EXISTS idx_scheduled_due ON scheduled_jobs(status,run_at);"""
def initialize_scheduler(db_path):
 with connect(db_path) as conn: conn.executescript(SCHEMA)
def schedule_job(db_path,kind,payload,run_at,idempotency_key):
 try:
  dt=datetime.fromisoformat(run_at.replace("Z","+00:00"))
  if dt.tzinfo is None: raise ValueError()
 except Exception as exc: raise ValueError("run_at must be timezone-aware ISO-8601") from exc
 if not isinstance(kind,str) or not kind.strip(): raise ValueError("kind is required")
 if not isinstance(payload,dict): raise ValueError("payload must be an object")
 if not isinstance(idempotency_key,str) or not idempotency_key or len(idempotency_key)>200: raise ValueError("idempotency_key is required (max 200 chars)")
 with connect(db_path) as conn:
  conn.execute("INSERT INTO scheduled_jobs(kind,payload_json,run_at,idempotency_key) VALUES(?,?,?,?)",
   (kind.strip(),json_dump(payload),dt.astimezone(timezone.utc).isoformat(),idempotency_key))
  return dict(conn.execute("SELECT * FROM scheduled_jobs WHERE idempotency_key=?",(idempotency_key,)).fetchone())
def enqueue_due(db_path,now=None,limit=50):
 if now is None: now=datetime.now(timezone.utc).isoformat()
 with connect(db_path) as conn:
  rows=conn.execute("SELECT * FROM scheduled_jobs WHERE status='scheduled' AND run_at<=? ORDER BY run_at,id LIMIT ?",
   (now,max(1,min(int(limit),200)))).fetchall()
 created=[]
 for row in rows:
  job=enqueue(db_path,row["kind"],json.loads(row["payload_json"]),row["idempotency_key"])
  with connect(db_path) as conn:
   conn.execute("UPDATE scheduled_jobs SET status='enqueued',enqueued_job_id=? WHERE id=? AND status='scheduled'",(job["id"],row["id"]))
  created.append({"schedule_id":row["id"],"job_id":job["id"]})
 return created
def list_scheduled(db_path):
 with connect(db_path) as conn: return [dict(r) for r in conn.execute("SELECT * FROM scheduled_jobs ORDER BY run_at LIMIT 200")]
