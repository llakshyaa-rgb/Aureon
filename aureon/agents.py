"""Dependency-aware supervised local agent plans."""
import uuid, json
from .db import connect, json_dump
from .jobs import enqueue

ALLOWED = {
 "design.brief": {"niche","audience","product_type","style","concept"},
 "creative.generate": {"title","concept","style","palette"},
 "creative.collection": {"title","concept","styles","palette"},
 "listing.draft": {"product","audience","keywords"},
 "support.triage": {"subject","message"},
 "marketing.draft": {"product_title","audience","channel","benefit","call_to_action"},
 "economics.calculate": {"channel","selling_price","product_cost"},
 "economics.compare": {"pod","dropshipping"},
 "economics.scenarios": {"offer"},
 "opportunity.assess": {"title","evidence","signals"},
 "research.competitors": {"observations"},
 "opportunity.evaluate": {"title","evidence","signals","observations","offer"},
 "supplier.order.prepare": {"product_title","quantity","product_type","destination","currency"},
 "campaign.metrics": {"metrics"},
 "trends.collect": {"geo"},
}
REFERENCE = {"$from", "path"}


def _validate_refs(value, current, deps):
    if isinstance(value, dict):
        if set(value) == REFERENCE:
            step = value["$from"]
            if isinstance(step, bool) or not isinstance(step, int) or step not in deps:
                raise ValueError("references must point to a declared dependency")
            path = value["path"]
            if not isinstance(path, str) or not path or len(path) > 160:
                raise ValueError("reference path must be non-empty text")
            return
        for child in value.values():
            _validate_refs(child, current, deps)
    elif isinstance(value, list):
        for child in value:
            _validate_refs(child, current, deps)


def plan_run(name, tasks):
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError("plan name required")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 20:
        raise ValueError("plan must contain 1..20 tasks")
    clean = []
    for i, task in enumerate(tasks):
        if not isinstance(task, dict) or task.get("kind") not in ALLOWED or not isinstance(task.get("payload"), dict):
            raise ValueError("unsupported task or payload")
        missing = ALLOWED[task["kind"]] - set(task["payload"])
        if missing:
            raise ValueError("task " + str(i) + " missing " + ", ".join(sorted(missing)))
        deps = task.get("depends_on", [])
        if not isinstance(deps, list) or any(
            isinstance(dep, bool) or not isinstance(dep, int) or dep < 0 or dep >= i for dep in deps
        ) or len(deps) != len(set(deps)):
            raise ValueError("dependencies must reference unique earlier step indexes")
        _validate_refs(task["payload"], i, deps)
        clean.append({"step": i, "kind": task["kind"], "payload": task["payload"], "depends_on": deps})
    return {"name": name.strip(), "tasks": clean, "mode": "supervised_local",
            "requires_operator_review": True, "execution": "dependency_ordered"}


def submit_plan(db_path, name, tasks, idempotency_key=None):
    plan = plan_run(name, tasks)
    if idempotency_key is not None and (not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 180):
        raise ValueError("idempotency_key must be 1-180 characters")
    key = idempotency_key or "plan-" + uuid.uuid4().hex
    with connect(db_path) as conn:
        rows = conn.execute("SELECT id,data_json FROM workspace_records WHERE kind='agent_run'").fetchall()
        for row in rows:
            existing_data = json.loads(row["data_json"])
            if existing_data.get("idempotency_key") == key:
                if existing_data.get("name") != plan["name"] or existing_data.get("tasks") != plan["tasks"]:
                    raise ValueError("idempotency_key already belongs to a different agent plan")
                return {"run_id": row["id"], "duplicate": True}
    job = enqueue(db_path, "agent.run", {"plan": plan}, key, max_attempts=1)
    with connect(db_path) as conn:
        existing_rows = conn.execute("SELECT id,data_json FROM workspace_records WHERE kind='agent_run'").fetchall()
        for existing in existing_rows:
            existing_data = json.loads(existing["data_json"])
            if existing_data.get("idempotency_key") == key:
                if existing_data.get("name") != plan["name"] or existing_data.get("tasks") != plan["tasks"]:
                    raise ValueError("idempotency_key already belongs to a different agent plan")
                return {"run_id": existing["id"], "job_ids": [job["id"]], "duplicate": True}
        cur = conn.execute("INSERT INTO workspace_records(kind,status,title,data_json) VALUES('agent_run','queued',?,?)",
            (plan["name"], json_dump({**plan, "idempotency_key": key, "job_ids": [job["id"]]})))
        run_id = cur.lastrowid
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("agent.run.queued", "agent_run", str(run_id), json_dump({"job_ids": [job["id"]]})))
    return {"run_id": run_id, "job_ids": [job["id"]], "duplicate": False, "mode": "supervised_local"}


def runtime_status(db_path):
    with connect(db_path) as conn:
        jobs = {r["status"]: r["n"] for r in conn.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status")}
        rows = conn.execute("SELECT id,status,title,created_at,data_json FROM workspace_records WHERE kind='agent_run' ORDER BY id DESC LIMIT 30").fetchall()
        runs = []
        for row in rows:
            data = json.loads(row["data_json"])
            ids = data.get("job_ids", [])
            states = []
            if ids:
                marks = ",".join("?" for _ in ids)
                states = [r["status"] for r in conn.execute("SELECT status FROM jobs WHERE id IN (" + marks + ")", ids).fetchall()]
            status = data.get("progress_status") or ("succeeded" if states and all(x == "succeeded" for x in states) else "failed" if any(x == "failed" for x in states) else "running" if any(x == "running" for x in states) else "queued")
            runs.append({"id": row["id"], "status": status, "title": row["title"], "created_at": row["created_at"],
                         "job_ids": ids, "job_statuses": states, "steps": data.get("tasks", []),
                         "progress": data.get("progress", []), "current_step": data.get("current_step"),
                         "completed_steps": data.get("completed_steps", 0), "warnings": data.get("warnings", [])})
    return {"jobs": jobs, "recent_runs": runs, "execution": "dependency-aware local worker",
            "shell_execution": False, "external_side_effects": False}
