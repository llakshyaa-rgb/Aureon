"""Persistent, idempotent scheduler with atomic due-job enqueue."""
import json
from datetime import datetime,timezone
from .db import connect,json_dump
WORKER_KINDS={"design.brief","listing.draft","support.triage","marketing.draft","economics.calculate","economics.compare","opportunity.assess","campaign.metrics","product.create"}
SCHEMA="""CREATE TABLE IF NOT EXISTS scheduled_jobs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,payload_json TEXT NOT NULL,
 run_at TEXT NOT NULL,idempotency_key TEXT UNIQUE,status TEXT NOT NULL DEFAULT 'scheduled',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),enqueued_job_id INTEGER
);CREATE INDEX IF NOT EXISTS idx_scheduled_due ON scheduled_jobs(status,run_at);"""
def _aware(value,label):
 if not isinstance(value,str): raise ValueError(label+" must be timezone-aware ISO-8601")
 try:
  parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
  if parsed.tzinfo is None: raise ValueError()
  return parsed.astimezone(timezone.utc)
 except Exception as exc: raise ValueError(label+" must be timezone-aware ISO-8601") from exc
def initialize_scheduler(db_path):
 with connect(db_path) as conn: conn.executescript(SCHEMA)
def schedule_job(db_path,kind,payload,run_at,idempotency_key):
 if not isinstance(kind,str) or kind not in WORKER_KINDS: raise ValueError("unsupported worker job kind")
 if not isinstance(payload,dict): raise ValueError("payload must be an object")
 if not isinstance(idempotency_key,str) or not idempotency_key.strip() or len(idempotency_key)>200: raise ValueError("idempotency_key is required (max 200 chars)")
 normalized=_aware(run_at,"run_at").isoformat()
 with connect(db_path) as conn:
  conn.execute("BEGIN IMMEDIATE")
  old=conn.execute("SELECT * FROM scheduled_jobs WHERE idempotency_key=?",(idempotency_key,)).fetchone()
  if old:
   if old["kind"]!=kind or old["payload_json"]!=json_dump(payload) or old["run_at"]!=normalized:
    raise ValueError("idempotency_key already belongs to a different scheduled job")
   return dict(old)
  cur=conn.execute("INSERT INTO scheduled_jobs(kind,payload_json,run_at,idempotency_key) VALUES(?,?,?,?)",
   (kind,json_dump(payload),normalized,idempotency_key))
  return dict(conn.execute("SELECT * FROM scheduled_jobs WHERE id=?",(cur.lastrowid,)).fetchone())
def enqueue_due(db_path,now=None,limit=50):
 current=datetime.now(timezone.utc) if now is None else _aware(now,"now")
 created=[]
 with connect(db_path) as conn:
  conn.execute("BEGIN IMMEDIATE")
  rows=conn.execute("SELECT * FROM scheduled_jobs WHERE status='scheduled' AND run_at<=? ORDER BY run_at,id LIMIT ?",
   (current.isoformat(),max(1,min(int(limit),200)))).fetchall()
  for row in rows:
   existing=conn.execute("SELECT * FROM jobs WHERE idempotency_key=?",(row["idempotency_key"],)).fetchone()
   if existing:
    if existing["kind"]!=row["kind"] or existing["payload_json"]!=row["payload_json"]:
     raise ValueError("scheduled idempotency key conflicts with an existing job")
    job_id=existing["id"]
   else:
    cur=conn.execute("INSERT INTO jobs(kind,payload_json,idempotency_key) VALUES(?,?,?)",
     (row["kind"],row["payload_json"],row["idempotency_key"]))
    job_id=cur.lastrowid
    conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
     ("job.queued","job",str(job_id),json_dump({"kind":row["kind"],"scheduled_id":row["id"]})))
   conn.execute("UPDATE scheduled_jobs SET status='enqueued',enqueued_job_id=? WHERE id=? AND status='scheduled'",(job_id,row["id"]))
   created.append({"schedule_id":row["id"],"job_id":job_id})
 return created
def list_scheduled(db_path):
 with connect(db_path) as conn: return [dict(r) for r in conn.execute("SELECT * FROM scheduled_jobs ORDER BY run_at LIMIT 200")]
