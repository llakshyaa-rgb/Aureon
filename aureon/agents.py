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
 "commerce.mission": {"product_title","concept","audience","product_type","destination","selling_price","product_cost","keywords","style","palette"},
}

OPTIONAL = {
 "commerce.mission": {"currency","geo","shipping_cost","platform_fee_rate","payment_fee_rate",
  "payment_fixed_fee","estimated_ad_cost","packaging_cost","duty_cost","other_costs",
  "tax_rate","return_rate","chargeback_rate","competitor_urls"},
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
        extra = set(task["payload"]) - ALLOWED[task["kind"]] - OPTIONAL.get(task["kind"], set())
        if missing:
            raise ValueError("task " + str(i) + " missing " + ", ".join(sorted(missing)))
        if extra:
            raise ValueError("task " + str(i) + " has unsupported fields: " + ", ".join(sorted(extra)))
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
    # Do not automatically replay a plan after partial execution; it may duplicate work.
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
        conn.execute("UPDATE jobs SET payload_json=? WHERE id=?",
                     (json_dump({"plan": plan, "run_id": run_id}), job["id"]))
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


def draft_plan(db_path, objective, context=None):
    """Ask the configured LLM for a safe local task graph; validate every task before returning it."""
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 1200:
        raise ValueError("objective must be 1-1200 characters")
    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if len(json.dumps(context, ensure_ascii=False)) > 12000:
        raise ValueError("planning context is too large")
    from .llm import generate
    system = (
        "You are Aureon's local workflow planner. Return only JSON with keys name, tasks, rationale. "
        "tasks is an array of 1-12 objects with kind, payload, and optional depends_on indexes. "
        "Only choose these safe local task kinds and exact payload fields: " +
        json.dumps({k: sorted(v) for k, v in ALLOWED.items()}) +
        ". When the objective is to research and prepare a product launch, prefer one commerce.mission task over separate disconnected tasks. "
        "A commerce.mission task executes Aureon's complete local product workflow and must include every required payload field. "
        + "Never add shell, network publishing, ad spend, payments, supplier ordering, customer messaging, "
        "deletion, or account changes. Do not fabricate observations or evidence. If inputs are missing, "
        "choose only tasks that can run with supplied context; otherwise explain gaps in rationale. "
        "Use earlier task indexes for dependencies. Never reference unavailable outputs."
    )
    prompt = "OBJECTIVE:\n" + objective.strip() + "\nCONTEXT:\n" + json.dumps(context, ensure_ascii=False)[:12000]
    response = generate(db_path, system, prompt, json_mode=True)
    raw = response.get("content", "").strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:]).rsplit("```", 1)[0].strip()
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise RuntimeError("The selected model did not return a valid workflow plan. Try another model or shorten the objective.") from None
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise RuntimeError("The selected model returned an invalid workflow plan.")
    plan = plan_run(data.get("name") or objective.strip()[:120], data["tasks"])
    return {"plan": plan, "rationale": data.get("rationale", ""),
            "provider": response.get("provider"), "model": response.get("model"),
            "requires_operator_review": True,
            "safety": "Only allowlisted local tasks are executable; external side effects remain approval-gated."}


def chat_command(db_path, message, history=None):
    """Conversational command interface: answer, ask a question, or queue an allowlisted local plan."""
    if not isinstance(message, str) or not message.strip() or len(message) > 12000:
        raise ValueError("message must be 1-12000 characters")
    if history is None:
        history = []
    if not isinstance(history, list) or len(history) > 12:
        raise ValueError("history must contain at most 12 messages")
    clean_history = []
    for item in history:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            clean_history.append({"role": item["role"], "content": content[:1600]})
    from .llm import generate
    system = (
        "You are Aureon, the user's conversational commerce operator. Reply ONLY as JSON with "
        "keys reply (string), tasks (array), and needs_input (string or empty). "
        "The user should be able to operate Aureon by describing goals in ordinary language. "
        "For simple questions or conversation, return tasks=[] and answer in reply. "
        "For a clear request to do work, create a short dependency-aware task plan using ONLY "
        "these allowlisted local task kinds and exact payload fields: "
        + json.dumps({k: sorted(v) for k, v in ALLOWED.items()})
        + ". For a request to research and prepare a product or product launch, prefer ONE commerce.mission task instead of splitting it into disconnected small tasks. "
        + "For commerce.mission, provide all required product inputs and include optional fee assumptions only when the user supplied them. "
        + "A commerce.mission runs Aureon's complete local product workflow: live trends/news collection, supplied competitor URL review, saved supplier-quote comparison, unit economics, product record, editable artwork, listing and launch-copy drafts, plus AI research analysis. "
        + "Use conservative explicit assumptions only where the mission code defines defaults; never invent evidence, supplier quotes, market demand, prices, stock, sales, or credentials. "
        "If essential input is missing, ask ONE concise question in needs_input and do not create tasks. "
        "Do not ask for information that can be safely left as an explicit assumption. "
        "Do not create tasks for publishing, spending, payment, placing supplier orders, customer messaging, "
        "deleting data, account changes, arbitrary code or shell execution. "
        "Only use dependencies on earlier task indexes. Never claim a task ran unless it is in the supplied results. "
        "Keep the reply concise and friendly."
    )
    # The browser sends the just-submitted user message in history as well.
    # Remove that duplicate so the model sees it exactly once.
    if clean_history and clean_history[-1]["role"] == "user" and clean_history[-1]["content"].strip() == message.strip():
        clean_history.pop()
    prompt = "RECENT CONVERSATION:\n" + json.dumps(clean_history, ensure_ascii=False)[:10000]
    prompt += "\nCURRENT USER MESSAGE:\n" + message.strip()
    response = generate(db_path, system, prompt, json_mode=True)
    raw = response.get("content", "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        start, end = raw.find("{"), raw.rfind("}")
        try:
            data = json.loads(raw[start:end + 1]) if start >= 0 and end > start else None
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict) or not isinstance(data.get("tasks", []), list):
        raise RuntimeError("The selected model did not return a usable chat response. Try again or change model.")
    if "reply" not in data or not isinstance(data.get("reply"), str):
        raise RuntimeError("The selected model returned an incomplete chat response. Try another model.")
    if "needs_input" in data and not isinstance(data.get("needs_input"), str):
        raise RuntimeError("The selected model returned an invalid follow-up question. Try another model.")
    reply = data.get("reply", "").strip()
    needs_input = data.get("needs_input", "").strip()
    # Reject the kind of one-word/echo response that previously made the
    # operator appear to accept a command without understanding it.
    if not data.get("tasks") and not needs_input and len(message.strip()) >= 80 and len(reply) < 20:
        raise RuntimeError("The selected model returned an incomplete answer. Try another model or switch providers.")
    if not isinstance(reply, str):
        reply = ""
    if not isinstance(needs_input, str):
        needs_input = ""
    tasks = data.get("tasks", [])
    if needs_input.strip():
        return {"reply": needs_input.strip(), "status": "needs_input",
                "provider": response.get("provider"), "model": response.get("model")}
    if not tasks:
        return {"reply": reply or "I'm here. What would you like me to work on?",
                "status": "answered", "provider": response.get("provider"), "model": response.get("model")}

    # Validate before queueing. If the model emits an almost-correct task schema,
    # give it one explicit repair attempt instead of failing with a raw validator error.
    plan_name = "Chat command · " + message.strip()[:90]
    try:
        plan = plan_run(plan_name, tasks)
    except (ValueError, TypeError, KeyError) as validation_error:
        repair_prompt = (
            "Your previous JSON response could not be queued because its task plan failed validation.\\n"
            "Validation error: " + str(validation_error) + "\\n"
            "Original user request:\\n" + message.strip() + "\\n"
            "Your previous JSON response:\\n" + json.dumps(data, ensure_ascii=False) + "\\n"
            "Return a corrected JSON object with exactly reply, tasks, and needs_input. "
            "Use only the task kinds and exact required/optional payload fields in the system instructions. "
            "Do not add explanatory text or unsupported fields. For a product launch, use one commerce.mission task."
        )
        repaired = generate(db_path, system, repair_prompt, json_mode=True)
        repaired_raw = repaired.get("content", "").strip()
        if repaired_raw.startswith("```"):
            repaired_raw = repaired_raw.split("\\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            repaired_data = json.loads(repaired_raw)
        except (TypeError, json.JSONDecodeError):
            start, end = repaired_raw.find("{"), repaired_raw.rfind("}")
            try:
                repaired_data = json.loads(repaired_raw[start:end + 1]) if start >= 0 and end > start else None
            except json.JSONDecodeError:
                repaired_data = None
        if not isinstance(repaired_data, dict) or not isinstance(repaired_data.get("tasks", []), list):
            raise RuntimeError("Aureon's AI produced an invalid task plan, even after one repair attempt. Check the selected model's JSON support.") from validation_error
        if repaired_data.get("needs_input"):
            return {"reply": str(repaired_data["needs_input"]), "status": "needs_input",
                    "provider": repaired.get("provider"), "model": repaired.get("model")}
        tasks = repaired_data.get("tasks", [])
        if not tasks:
            return {"reply": str(repaired_data.get("reply") or "I couldn't safely turn that into a task yet."),
                    "status": "answered", "provider": repaired.get("provider"), "model": repaired.get("model")}
        try:
            plan = plan_run(plan_name, tasks)
            response = repaired
            reply = str(repaired_data.get("reply") or reply)
        except (ValueError, TypeError, KeyError) as final_error:
            raise RuntimeError("Aureon's AI returned an unsupported task plan twice. Last validation issue: " + str(final_error)) from final_error

    queued = submit_plan(db_path, plan["name"], plan["tasks"])
    return {"reply": reply or "I've prepared the requested local workflow.",
            "status": "queued", "run_id": queued["run_id"], "job_ids": queued.get("job_ids", []),
            "tasks": plan["tasks"], "provider": response.get("provider"), "model": response.get("model"),
            "safety": "Only allowlisted local tasks were queued. External publishing, spending and supplier orders remain disabled."}
