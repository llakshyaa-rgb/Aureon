import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from aureon.db import initialize
from aureon.intelligence.product_research import analyze_competition
from aureon.creative import validate_svg_artwork
from aureon.agents import submit_plan, runtime_status
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

    def tearDown(self):
        self.tmp.cleanup()

    def test_independent_steps_continue_and_persist_after_one_failure(self):
        plan = submit_plan(self.db, "Partial recovery test", [
            {"kind": "design.brief", "payload": {
                "niche": "space", "audience": "students",
                "product_type": "tee", "style": "minimal", "concept": "planets"}},
            {"kind": "trends.collect", "payload": {"geo": "IN", "limit": 5}},
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
