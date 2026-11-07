"""Objective-driven local commerce mission runner.

This is deterministic orchestration, not an LLM. It runs useful local work
without requiring the operator to click through each feature separately.
External publishing, spending and supplier orders are deliberately excluded.
"""
import json
import math
import os
import re
import uuid
from urllib.request import Request, urlopen
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
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
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
        conn.execute("UPDATE jobs SET payload_json=? WHERE id=?", (json_dump({**payload, "run_id": run_id}), job["id"]))
        conn.execute(
            "INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
            ("agent.mission.queued", "agent_run", str(run_id),
             json_dump({"job_id": job["id"], "product_title": title})))
    return {"run_id": run_id, "job_id": job["id"], "duplicate": False,
            "mode": "autonomous_local", "message": "Mission queued for the background worker."}


def _ai_review(db_path, context):
    """Use the operator-selected provider; model output is advisory, never source evidence."""
    from .llm import generate
    system = (
        "You are Aureon's evidence-bound commerce analyst. Use only supplied observations. "
        "Never invent demand, supplier facts, sales, prices, costs, ratings or citations. "
        "Label assumptions, explain uncertainty, and recommend no paid or irreversible action. "
        "Return a JSON object with executive_summary, opportunities, risks, recommended_next_steps, "
        "confidence (low, medium, or high), and missing_evidence."
    )
    prompt = (
        "Review this commerce mission context. Give practical, specific next steps. "
        "Do not claim that attention signals prove purchase demand. Do not treat unverified "
        "operator-entered supplier quotes as verified. Do not include unsupported numerical claims.\n\n"
        + json.dumps(context, ensure_ascii=False)[:22000]
    )
    result = generate(db_path, system, prompt, json_mode=True)
    try:
        analysis = json.loads(result["content"])
    except json.JSONDecodeError:
        # Some compatible models ignore JSON mode; retain their answer as text rather than fail the mission.
        analysis = {"executive_summary": result["content"], "format_warning": "Model did not return JSON."}
    if not isinstance(analysis, dict):
        analysis = {"executive_summary": str(analysis)}
    return {"status": "completed", "provider": result["provider"], "model": result["model"],
            "analysis": analysis,
            "warning": "AI advice is not verified market evidence; review before acting."}


def _ai_work(db_path, payload, context):
    """Generate usable listing/launch assets and an evidence-bound analysis."""
    from .llm import generate
    system = (
        "You are Aureon's commerce operator. Return only a JSON object with keys "
        "listing_title (string), listing_description (string), tags (array of short strings), "
        "marketing_headline (string), marketing_copy (string), research_analysis (object with "
        "executive_summary, opportunities, risks, recommended_next_steps, confidence, "
        "missing_evidence). Use only supplied facts. You may write creative copy, but never "
        "invent product specifications, certifications, supplier facts, demand, reviews, sales "
        "or performance. Mark assumptions and avoid guarantees. No paid/irreversible actions."
    )
    prompt = (
        "Prepare a useful draft listing and launch copy for this product, then assess the "
        "evidence and economics. Use audience-appropriate language. Include practical risks "
        "and evidence gaps.\n\nPRODUCT INPUT:\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nRESEARCH CONTEXT:\n"
        + json.dumps(context, ensure_ascii=False)[:18000]
    )
    response = generate(db_path, system, prompt, json_mode=True)
    try:
        data = json.loads(response["content"])
    except json.JSONDecodeError:
        raise RuntimeError("Selected model did not return valid JSON. Try another model or lower output complexity.")
    if not isinstance(data, dict):
        raise RuntimeError("Selected model returned an invalid structured response.")
    for field in ("listing_title", "listing_description", "marketing_headline", "marketing_copy"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise RuntimeError("Selected model omitted required field: " + field)
    tags = data.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(x, str) for x in tags):
        tags = payload["keywords"]
    data["tags"] = [x.strip()[:80] for x in tags if x.strip()][:20]
    data["_provider"] = response["provider"]
    data["_model"] = response["model"]
    return {"status": "completed", "provider": response["provider"], "model": response["model"], "assets": data}


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
            if isinstance(value, dict) and value.get("status") == "not_configured":
                steps.append({"name": name, "status": "not_configured", "output": value})
                warnings.append(name + ": AI provider is not configured.")
            else:
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
    research_context = {"market_signals": trends, "supplier_comparison": comparison,
                        "unit_economics": economics, "cost_assumptions": cost_source}
    ai_work = step("AI listing, launch assets and research analysis",
                   lambda: _ai_work(db_path, payload, research_context))
    ai_assets = ai_work.get("assets", {}) if isinstance(ai_work, dict) else {}
    product = step("Product workspace record",
        lambda: create_record(db_path, "product", payload["product_title"], {
            "product_type": payload["product_type"], "selling_price": payload["selling_price"],
            "cost": product_cost, "currency": payload["currency"],
            "vendor": best["supplier"] if best else "",
            "description": ai_assets.get("listing_description", payload["concept"]),
            "tags": ai_assets.get("tags", payload["keywords"]),
            "source": "Aureon autonomous mission",
            "cost_assumption": cost_source,
        }, "research"))
    artwork = step("Editable design artwork",
        lambda: create_asset(db_path, title=payload["product_title"],
                             concept=payload["concept"], style=payload["style"],
                             palette=payload["palette"]))
    def listing_record():
        draft = ({"title": ai_assets["listing_title"],
                  "description": ai_assets["listing_description"],
                  "tags": ai_assets["tags"], "audience": payload["audience"],
                  "generated_by": "configured_llm"}
                 if ai_assets else generate_listing_draft(
                     {"title": payload["product_title"], "features": payload["concept"]},
                     payload["audience"], payload["keywords"]))
        return create_record(db_path, "listing", draft["title"], draft, "draft")
    listing = step("Listing draft", listing_record)
    def marketing_record():
        draft = ({"headline": ai_assets["marketing_headline"],
                  "copy": ai_assets["marketing_copy"], "channel": "instagram",
                  "audience": payload["audience"], "generated_by": "configured_llm"}
                 if ai_assets else draft_marketing_content(
                     payload["product_title"], payload["audience"], "instagram",
                     payload["concept"], "Explore the collection"))
        return create_record(db_path, "campaign",
            "Draft · " + payload["product_title"], {"draft": draft}, "draft")
    marketing = step("Launch copy draft", marketing_record)
    ai_review = ({"status": "completed", "provider": ai_work.get("provider"),
                  "model": ai_work.get("model"), "analysis": ai_assets.get("research_analysis"),
                  "warning": "AI-generated copy and analysis are drafts, not verified facts."}
                 if ai_assets else {"status": "unavailable",
                  "message": "AI assets unavailable; deterministic draft fallbacks were used."})

    result = {
        "mode": "autonomous_local_workflow",
        "ai_review": ai_review,
        "planner": ("deterministic safe workflow with AI analyst review" if isinstance(ai_review, dict) and ai_review.get("status") == "completed" else "deterministic safe workflow; configure an LLM in Settings for AI analysis"),
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
