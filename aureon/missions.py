"""Objective-driven local commerce mission runner.

This is deterministic orchestration, not an LLM. It runs useful local work
without requiring the operator to click through each feature separately.
External publishing, spending and supplier orders are deliberately excluded.
"""
import json
import re
import uuid
from .db import connect, json_dump
from .jobs import enqueue


def _text(value, name, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(name + " is required (max " + str(limit) + " characters)")
    return value.strip()


def submit_mission(db_path, body):
    if not isinstance(body, dict):
        raise ValueError("mission request must be an object")
    title = _text(body.get("product_title"), "product_title", 160)
    concept = _text(body.get("concept"), "concept", 240)
    audience = _text(body.get("audience"), "audience", 160)
    product_type = _text(body.get("product_type"), "product_type", 100)
    destination = _text(body.get("destination"), "destination", 100)
    currency = _text(body.get("currency", "INR"), "currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter code")
    geo = _text(body.get("geo", "IN"), "geo", 2).upper()
    if not re.fullmatch(r"[A-Z]{2}", geo):
        raise ValueError("geo must be a two-letter country code")
    def money(key, default=None, positive=False):
        value = body.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(key + " must be a non-negative number")
        if positive and value <= 0:
            raise ValueError(key + " must be greater than zero")
        return round(float(value), 2)
    selling_price = money("selling_price", positive=True)
    product_cost = money("product_cost")
    shipping_cost = money("shipping_cost", 0)
    keywords = body.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [x.strip() for x in keywords.split(",") if x.strip()]
    if not isinstance(keywords, list) or not 1 <= len(keywords) <= 12 or any(not isinstance(x, str) or not x.strip() or len(x) > 80 for x in keywords):
        raise ValueError("keywords must contain 1-12 non-empty terms")
    payload = {
        "product_title": title, "concept": concept, "audience": audience,
        "product_type": product_type, "destination": destination,
        "currency": currency, "geo": geo, "selling_price": selling_price,
        "product_cost": product_cost, "shipping_cost": shipping_cost,
        "keywords": [x.strip() for x in keywords], "style": body.get("style", "orbit"),
        "palette": body.get("palette", "midnight"),
    }
    if payload["style"] not in {"orbit", "badge", "type", "botanical", "geometric"}:
        raise ValueError("unsupported artwork style")
    if payload["palette"] not in {"midnight", "sunset", "forest", "mono", "ocean"}:
        raise ValueError("unsupported artwork palette")
    key = body.get("idempotency_key") or "mission-" + uuid.uuid4().hex
    if not isinstance(key, str) or not key.strip() or len(key) > 180:
        raise ValueError("invalid idempotency key")
    job = enqueue(db_path, "commerce.mission", payload, key, max_attempts=2)
    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id,data_json FROM workspace_records WHERE kind='agent_run'").fetchall()
        for row in existing:
            data = json.loads(row["data_json"])
            if data.get("idempotency_key") == key:
                return {"run_id": row["id"], "job_id": job["id"], "duplicate": True}
        plan = {
            "name": "Commerce mission · " + title,
            "mode": "autonomous_local",
            "requires_operator_review": True,
            "execution": "background_worker",
            "tasks": [
                {"kind": "trends.collect", "label": "Collect live market attention signals"},
                {"kind": "research.suppliers", "label": "Compare matching saved supplier quotes"},
                {"kind": "economics.calculate", "label": "Calculate estimated unit economics"},
                {"kind": "product.create", "label": "Create product workspace record"},
                {"kind": "creative.generate", "label": "Generate editable design artwork"},
                {"kind": "listing.draft", "label": "Prepare listing draft"},
                {"kind": "marketing.draft", "label": "Prepare launch copy"},
            ],
            "job_ids": [job["id"]], "idempotency_key": key,
        }
        cur = conn.execute(
            "INSERT INTO workspace_records(kind,status,title,data_json) VALUES('agent_run','queued',?,?)",
            (plan["name"], json_dump(plan)))
        run_id = cur.lastrowid
        conn.execute(
            "INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("agent.mission.queued", "agent_run", str(run_id),
             json_dump({"job_id": job["id"], "product_title": title})))
    return {"run_id": run_id, "job_id": job["id"], "duplicate": False,
            "mode": "autonomous_local", "message": "Mission queued for the background worker."}


def run_mission(db_path, payload):
    from .trends import collect_trends
    from .suppliers import compare_supplier_quotes
    from .intelligence.economics import Offer, calculate_unit_economics
    from .creative import create_asset
    from .commerce import generate_listing_draft, draft_marketing_content
    from .workflows import create_record

    steps = []
    warnings = []
    def step(name, fn):
        try:
            value = fn()
            steps.append({"name": name, "status": "succeeded", "output": value})
            return value
        except Exception as exc:
            steps.append({"name": name, "status": "needs_attention", "error": str(exc)})
            warnings.append(name + ": " + str(exc))
            return None

    trends = step("Live market attention signals",
                  lambda: collect_trends(db_path, payload["geo"], 25))
    comparison = step("Supplier quote comparison",
                      lambda: compare_supplier_quotes(db_path, payload["product_type"],
                                                      payload["destination"], payload["currency"]))
    best = comparison.get("best_quote") if comparison else None
    if best:
        product_cost = best["quote"]["product_cost"]
        shipping_cost = best["quote"]["shipping_cost"]
        cost_source = "saved operator-entered supplier quote #" + str(best["supplier_id"])
    else:
        product_cost = payload["product_cost"]
        shipping_cost = payload["shipping_cost"]
        cost_source = "operator-provided estimate; no matching supplier quote found"
        warnings.append("No matching supplier quote was available; economics use the supplied cost assumptions.")

    economics = step("Unit economics",
        lambda: calculate_unit_economics(Offer(
            channel="POD / dropshipping estimate",
            selling_price=payload["selling_price"], product_cost=product_cost,
            shipping_cost=shipping_cost, currency=payload["currency"])))
    product = step("Product workspace record",
        lambda: create_record(db_path, "product", payload["product_title"], {
            "product_type": payload["product_type"], "selling_price": payload["selling_price"],
            "cost": product_cost, "currency": payload["currency"],
            "vendor": best["supplier"] if best else "",
            "description": payload["concept"], "tags": payload["keywords"],
            "source": "Aureon autonomous mission",
            "cost_assumption": cost_source,
        }, "research"))
    artwork = step("Editable design artwork",
        lambda: create_asset(db_path, title=payload["product_title"],
                             concept=payload["concept"], style=payload["style"],
                             palette=payload["palette"]))
    listing = step("Listing draft",
        lambda: (lambda draft: create_record(db_path, "listing", draft["title"], draft, "draft"))(
            generate_listing_draft(
                {"title": payload["product_title"], "features": payload["concept"]},
                payload["audience"], payload["keywords"])))
    marketing = step("Launch copy draft",
        lambda: (lambda draft: create_record(db_path, "campaign",
            "Draft · " + payload["product_title"], {"draft": draft}, "draft"))(
            draft_marketing_content(payload["product_title"], payload["audience"],
                                    "instagram", payload["concept"], "Explore the collection")))

    result = {
        "mode": "autonomous_local_workflow",
        "planner": "deterministic local orchestration; no LLM is connected",
        "product_title": payload["product_title"],
        "status": "completed_with_warnings" if warnings else "completed",
        "steps": steps,
        "outputs": {
            "trend_collection": trends,
            "supplier_comparison": comparison,
            "economics": economics,
            "product": product,
            "artwork": ({"record_id": artwork["record"]["id"], "qa": artwork["artwork"].get("qa")}
                        if artwork else None),
            "listing": ({"record_id": listing["id"], "title": listing["title"]} if listing else None),
            "marketing_draft": ({"record_id": marketing["id"], "title": marketing["title"]}
                                if marketing else None),
        },
        "assumptions": {
            "supplier_cost_source": cost_source,
            "taxes_fees_returns_ads": "not included unless separately supplied",
            "trend_data": "attention signals only; not validated product demand",
            "supplier_quotes": "operator-entered and unverified",
        },
        "warnings": warnings,
        "approval_required_before": ["publishing", "ad spend", "supplier orders", "customer commitments"],
        "external_actions_taken": False,
    }
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("agent.mission.completed", "agent_run", str(payload.get("run_id", "unknown")),
             json_dump({"status": result["status"], "warnings": warnings,
                        "output_record_ids": [x for x in [
                            product.get("id") if product else None,
                            artwork["record"]["id"] if artwork else None,
                            listing.get("id") if listing else None,
                            marketing.get("id") if marketing else None] if x is not None]})))
    return result
