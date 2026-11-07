import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from aureon.db import initialize, connect, json_dump
from aureon.workflows import initialize_workspace
from aureon.intelligence.product_research import analyze_competition
from aureon.creative import validate_svg_artwork
from aureon.agents import submit_plan, runtime_status, draft_plan, plan_run
from aureon.worker import run_once


class ResearchQualityTests(unittest.TestCase):
    def test_competitor_analysis_reports_distribution_and_sample_confidence(self):
        now = datetime.now(timezone.utc)
        rows = []
        for i, price in enumerate((500, 700, 900)):
            rows.append({
                "url": "https://shop" + str(i) + ".example/products/item",
                "price": price, "currency": "INR", "reviews": i * 10,
                "availability": "in stock",
                "collected_at": (now - timedelta(days=i)).isoformat(),
            })
        result = analyze_competition(rows)
        self.assertEqual(result["price_median"], 700)
        self.assertEqual(result["price_spread"], 400)
        self.assertEqual(result["sample_confidence"], "low")
        self.assertEqual(result["freshness"], "fresh")
        self.assertEqual(result["source_domain_count"], 3)

    def test_competitor_analysis_marks_old_sample_stale(self):
        old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        result = analyze_competition([{
            "url": "https://example.com/product", "price": 100,
            "currency": "INR", "reviews": 0, "collected_at": old,
        }])
        self.assertEqual(result["freshness"], "stale")
        self.assertEqual(result["sample_confidence"], "low")

    def test_svg_quality_rejects_mismatched_dimensions(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000"><text x="500" y="500" font-size="50">TEST</text></svg>'
        result = validate_svg_artwork(svg, width=4500, height=5400)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["declared_dimensions_match"])

    def test_svg_quality_rejects_text_outside_safe_area(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="4500" height="5400" viewBox="0 0 4500 5400"><text x="10" y="500" font-size="50">TEST</text></svg>'
        result = validate_svg_artwork(svg)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["safe_area"])


class AgentExecutionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "aureon.sqlite3"
        initialize(self.db)
        initialize_workspace(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_adaptive_plan_uses_model_and_validates_allowlisted_tasks(self):
        response = {"provider": "test-provider", "model": "test-model",
                    "content": """```json
{"name":"Design workflow","tasks":[{"kind":"design.brief","payload":{"niche":"space","audience":"students","product_type":"tee","style":"minimal","concept":"planets"}}],"rationale":"Create a first design brief."}
```"""}
        with patch("aureon.llm.generate", return_value=response):
            result = draft_plan(self.db, "Create a space-themed shirt design", {"audience": "students"})
        self.assertEqual(result["provider"], "test-provider")
        self.assertEqual(result["plan"]["tasks"][0]["kind"], "design.brief")
        self.assertTrue(result["requires_operator_review"])

    def test_plan_rejects_unsupported_payload_fields(self):
        with self.assertRaises(ValueError):
            plan_run("Unsafe fields", [{"kind": "trends.collect",
                "payload": {"geo": "IN", "shell": "rm -rf /"}}])

    def test_interrupted_plan_resumes_without_replaying_completed_steps(self):
        from aureon.jobs import recover_interrupted, list_jobs
        plan = submit_plan(self.db, "Resume test", [
            {"kind": "design.brief", "payload": {
                "niche": "space", "audience": "students",
                "product_type": "tee", "style": "minimal", "concept": "planets"}},
            {"kind": "trends.collect", "payload": {"geo": "IN"}},
        ])
        with connect(self.db) as conn:
            job = conn.execute("SELECT id FROM jobs ORDER BY id DESC LIMIT 1").fetchone()
            row = conn.execute("SELECT data_json FROM workspace_records WHERE id=?", (plan["run_id"],)).fetchone()
            data = __import__("json").loads(row["data_json"])
            data["step_states"] = ["succeeded", "pending"]
            data["step_outputs"] = [{"mode": "local", "kind": "design.brief", "result": {"draft": {"saved": True}}}, None]
            conn.execute("UPDATE workspace_records SET data_json=? WHERE id=?",
                         (json_dump(data), plan["run_id"]))
            conn.execute("UPDATE jobs SET status='running',attempts=1 WHERE id=?", (job["id"],))
        self.assertEqual(recover_interrupted(self.db)["requeued"], 1)
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch("aureon.worker.build_design_brief", side_effect=AssertionError("completed step replayed")))
            stack.enter_context(patch("aureon.worker.collect_trends", return_value={"created": 0}))
            outcome = run_once(self.db)
        self.assertEqual(outcome["status"], "succeeded")
        states = [x["status"] for x in outcome["result"]["result"]["steps"]]
        self.assertEqual(states, ["succeeded", "succeeded"])
        self.assertEqual(list_jobs(self.db)[0]["attempts"], 2)

    def test_independent_steps_continue_and_persist_after_one_failure(self):
        plan = submit_plan(self.db, "Partial recovery test", [
            {"kind": "design.brief", "payload": {
                "niche": "space", "audience": "students",
                "product_type": "tee", "style": "minimal", "concept": "planets"}},
            {"kind": "trends.collect", "payload": {"geo": "IN"}},
        ])
        with patch("aureon.worker.collect_trends", side_effect=RuntimeError("temporary network failure")):
            outcome = run_once(self.db)
        self.assertEqual(outcome["status"], "succeeded")
        result = outcome["result"]["result"]
        self.assertEqual(result["status"], "completed_with_warnings")
        self.assertEqual(result["steps"][0]["status"], "succeeded")
        self.assertEqual(result["steps"][1]["status"], "failed")
        run = runtime_status(self.db)["recent_runs"][0]
        self.assertEqual(run["status"], "completed_with_warnings")
        self.assertEqual(run["completed_steps"], 2)
        self.assertTrue(run["warnings"])


if __name__ == "__main__":
    unittest.main()
