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
        self.news_patch = patch("aureon.trends.collect_keyword_research",
                                return_value={"created": 0, "fetched": 0, "errors": [], "sources": []})
        self.news_patch.start()
        self.addCleanup(self.news_patch.stop)
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


    @patch("aureon.missions._ai_work", return_value={"status": "completed", "provider": "test", "model": "test", "assets": {"listing_title": "TEST listing", "listing_description": "Draft", "tags": ["test"], "marketing_headline": "Launch", "marketing_copy": "Draft copy", "research_analysis": {"executive_summary": "Evidence is limited.", "confidence": "low"}}})
    @patch("aureon.creative.create_asset", return_value={"record": {"id": 900}, "artwork": {"qa": {"passed": True}}})
    @patch("aureon.suppliers.compare_supplier_quotes", return_value={"quotes": [], "best_quote": None})
    @patch("aureon.trends.collect_trends", return_value={"created": 0})
    def test_mission_keeps_landed_cost_and_builds_evidence_chart(self, trends, quotes, artwork, ai):
        with patch("aureon.intelligence.economics.calculate_unit_economics",
                   return_value={"currency": "INR", "selling_price": 1499, "total_cost": 770,
                                 "fulfilment_cost": 770, "platform_fee": 0, "payment_fee": 0,
                                 "estimated_tax": 0, "return_reserve": 0, "chargeback_reserve": 0,
                                 "advertising_cost": 0, "other_costs": 0, "break_even_ad_cost": 729,
                                 "estimated_profit": 729, "profit_margin": 729 / 1499}):
            result = run_mission(self.db, self.payload)
        product = next(row for row in list_records(self.db, "product", 250))
        self.assertEqual(product["data"]["landed_cost"], 770)
        self.assertEqual(product["data"]["product_cost"], 650)
        self.assertEqual(product["data"]["shipping_cost"], 120)
        self.assertTrue(result["ai_review"]["analysis"]["data_visuals"])
        self.assertEqual(result["ai_review"]["analysis"]["metrics"]["estimated_profit"], 729)

    def test_interrupted_mission_resumes_without_duplicate_product_record(self):
        from contextlib import ExitStack
        from aureon.jobs import list_jobs
        from aureon.workflows import create_record as real_create_record

        submitted = submit_mission(self.db, {**self.payload, "idempotency_key": "mission-checkpoint"})
        job_payload = list_jobs(self.db)[0]["payload"]
        first_product_write = {"crash": True}

        def create_then_interrupt(*args, **kwargs):
            record = real_create_record(*args, **kwargs)
            if args[1] == "product" and first_product_write["crash"]:
                first_product_write["crash"] = False
                raise KeyboardInterrupt("simulated process termination after database commit")
            return record

        ai = {"status": "completed", "provider": "test", "model": "test",
              "assets": {"listing_title": "Draft listing", "listing_description": "Draft",
                         "tags": ["mountain"], "marketing_headline": "Launch",
                         "marketing_copy": "Draft copy", "research_analysis": {}}}
        news = {"created": 0, "fetched": 0, "errors": [], "sources": []}
        quotes = {"quotes": [], "best_quote": None}

        with ExitStack() as stack:
            stack.enter_context(patch("aureon.trends.collect_trends", return_value={"created": 0}))
            stack.enter_context(patch("aureon.trends.collect_keyword_research", return_value=news))
            stack.enter_context(patch("aureon.suppliers.compare_supplier_quotes", return_value=quotes))
            stack.enter_context(patch("aureon.missions._ai_work", return_value=ai))
            stack.enter_context(patch("aureon.creative.create_asset",
                                       return_value={"record": {"id": 999}, "artwork": {"qa": {"passed": True}}}))
            stack.enter_context(patch("aureon.workflows.create_record", side_effect=create_then_interrupt))
            with self.assertRaises(KeyboardInterrupt):
                run_mission(self.db, job_payload)

        with ExitStack() as stack:
            stack.enter_context(patch("aureon.trends.collect_trends",
                                      side_effect=AssertionError("completed trends step replayed")))
            stack.enter_context(patch("aureon.trends.collect_keyword_research",
                                      side_effect=AssertionError("completed news step replayed")))
            stack.enter_context(patch("aureon.suppliers.compare_supplier_quotes",
                                      side_effect=AssertionError("completed quote step replayed")))
            stack.enter_context(patch("aureon.missions._ai_work",
                                      side_effect=AssertionError("completed AI step replayed")))
            stack.enter_context(patch("aureon.creative.create_asset",
                                       return_value={"record": {"id": 999}, "artwork": {"qa": {"passed": True}}}))
            result = run_mission(self.db, job_payload)

        products = list_records(self.db, "product", 250)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["id"], result["outputs"]["product"]["id"])
        self.assertEqual(result["status"], "completed_with_warnings")
        self.assertTrue(any(step.get("resumed") for step in result["steps"]))

    def test_run_mission_defaults_missing_shipping_cost_to_zero(self):
        from contextlib import ExitStack
        payload = dict(self.payload)
        payload.pop("shipping_cost")
        ai = {"status": "completed", "provider": "test", "model": "test", "assets": {
            "listing_title": "Draft", "listing_description": "Draft", "tags": [],
            "marketing_headline": "Launch", "marketing_copy": "Draft", "research_analysis": {}}}
        with ExitStack() as stack:
            stack.enter_context(patch("aureon.trends.collect_trends", return_value={"created": 0}))
            stack.enter_context(patch("aureon.trends.collect_keyword_research", return_value={"created": 0, "fetched": 0, "errors": [], "sources": []}))
            stack.enter_context(patch("aureon.public_pages.research_competitor_urls", return_value={"requested": 0, "observed": [], "errors": []}))
            stack.enter_context(patch("aureon.suppliers.compare_supplier_quotes", return_value={"quotes": [], "best_quote": None}))
            stack.enter_context(patch("aureon.creative.create_asset", return_value={"record": {"id": 901}, "artwork": {"qa": {"passed": True}}}))
            stack.enter_context(patch("aureon.missions._ai_work", return_value=ai))
            stack.enter_context(patch("aureon.intelligence.economics.calculate_unit_economics", return_value={"currency": "INR", "selling_price": 1499, "total_cost": 650, "fulfilment_cost": 650, "estimated_profit": 849, "profit_margin": 849 / 1499}))
            result = run_mission(self.db, payload)
        self.assertIn(result["status"], {"completed", "completed_with_warnings"})
        product = next(row for row in list_records(self.db, "product", 250))
        self.assertEqual(product["data"]["shipping_cost"], 0)

    def test_mission_accepts_optional_cost_assumptions(self):
        result = submit_mission(self.db, {**self.payload, "platform_fee_rate": 0.05,
            "payment_fee_rate": 0.02, "estimated_ad_cost": 80, "tax_rate": 0.03})
        self.assertFalse(result["duplicate"])

    def test_rejects_invalid_fee_rate(self):
        with self.assertRaises(ValueError):
            submit_mission(self.db, {**self.payload, "platform_fee_rate": 1.5})

    def test_rejects_invalid_money_and_currency(self):
        with self.assertRaises(ValueError):
            submit_mission(self.db, {**self.payload, "selling_price": float("nan")})
        with self.assertRaises(ValueError):
            submit_mission(self.db, {**self.payload, "currency": "RUPEES"})

    @patch("aureon.missions._ai_work", return_value={"status": "completed", "provider": "test", "model": "test", "assets": {"listing_title": "TEST listing", "listing_description": "Draft", "tags": ["test"], "marketing_headline": "Launch", "marketing_copy": "Draft copy", "research_analysis": {}}})
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
