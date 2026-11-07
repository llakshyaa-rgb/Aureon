import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aureon.db import initialize
from aureon.workflows import initialize_workspace, list_records
from aureon.missions import submit_mission, run_mission


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "aureon.sqlite3"
        initialize(self.db)
        initialize_workspace(self.db)
        self.payload = {
            "product_title": "TEST - Mountain Hoodie",
            "concept": "Minimalist mountain artwork",
            "audience": "Outdoor enthusiasts",
            "product_type": "Apparel",
            "destination": "India",
            "currency": "INR",
            "geo": "IN",
            "selling_price": 1499,
            "product_cost": 650,
            "shipping_cost": 120,
            "keywords": ["mountain", "hiking"],
            "style": "orbit",
            "palette": "midnight",
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_submit_mission_queues_one_job_and_run(self):
        result = submit_mission(self.db, self.payload)
        self.assertEqual(result["mode"], "autonomous_local")
        self.assertFalse(result["duplicate"])
        duplicate = submit_mission(self.db, {**self.payload,
            "idempotency_key": "mission-repeat"})
        repeated = submit_mission(self.db, {**self.payload,
            "idempotency_key": "mission-repeat"})
        self.assertFalse(duplicate["duplicate"])
        self.assertTrue(repeated["duplicate"])

    def test_rejects_invalid_money_and_currency(self):
        with self.assertRaises(ValueError):
            submit_mission(self.db, {**self.payload, "selling_price": float("nan")})
        with self.assertRaises(ValueError):
            submit_mission(self.db, {**self.payload, "currency": "RUPEES"})

    @patch("aureon.missions._ai_review", return_value={"status": "not_configured"})
    @patch("aureon.creative.create_asset", return_value={
        "record": {"id": 900}, "artwork": {"qa": {"passed": True}}})
    @patch("aureon.commerce.generate_listing_draft", return_value={
        "title": "TEST listing", "description": "Draft", "tags": ["test"]})
    @patch("aureon.commerce.draft_marketing_content", return_value={
        "channel": "instagram", "copy": "Draft copy"})
    @patch("aureon.suppliers.compare_supplier_quotes", return_value={
        "quotes": [], "best_quote": None})
    @patch("aureon.trends.collect_trends", return_value={"created": 0})
    def test_run_mission_creates_product_listing_and_campaign_records(
        self, trends, quotes, marketing, listing, artwork, ai):
        from aureon.intelligence.economics import calculate_unit_economics
        with patch("aureon.intelligence.economics.calculate_unit_economics",
                   return_value={"currency": "INR", "estimated_profit": 729}):
            result = run_mission(self.db, self.payload)
        self.assertEqual(result["status"], "completed_with_warnings")
        kinds = {row["kind"] for row in list_records(self.db, None, 250)}
        self.assertTrue({"product", "listing", "campaign"}.issubset(kinds))
        self.assertFalse(result["external_actions_taken"])


if __name__ == "__main__":
    unittest.main()
