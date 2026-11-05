import tempfile
import unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace, add_finance_entry
from aureon.creative import generate_vector_artwork, generate_mockup_preview, validate_svg_artwork, create_asset, list_assets, create_collection
from aureon.intelligence.product_research import analyze_competition
from aureon.intelligence.economics import Offer
from aureon.intelligence.scenarios import pricing_scenarios, break_even_orders
from aureon.finance_reports import profit_and_loss
from aureon.agents import plan_run, submit_plan
from aureon.jobs import list_jobs
from aureon.worker import run_once


class ExtendedCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "a.sqlite3"
        initialize(self.db)
        initialize_workspace(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_vector_artwork_is_valid_and_editable(self):
        art = generate_vector_artwork("Orbit Club", "A calm planetary design")
        self.assertTrue(art["editable"])
        self.assertTrue(art["qa"]["passed"])
        self.assertIn("<svg", art["svg"])
        self.assertTrue(validate_svg_artwork(art["svg"])["passed"])
        mockup = generate_mockup_preview(art)
        self.assertEqual(mockup["kind"], "illustrative_flat_mockup")
        self.assertIn("<svg", mockup["svg"])
        with self.assertRaises(ValueError):
            generate_vector_artwork("Bad", "Unsafe", accent="url(javascript:alert(1))")
        with self.assertRaises(ValueError):
            validate_svg_artwork('<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>')
        with self.assertRaises(ValueError):
            validate_svg_artwork('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://bad.example/x"/></svg>')

    def test_artwork_asset_persists_and_can_be_listed(self):
        result = create_asset(self.db, title="Night Garden", concept="Leaves under stars",
                              style="botanical", palette="forest")
        self.assertEqual(result["record"]["status"], "generated")
        self.assertEqual(len(list_assets(self.db)), 1)

    def test_collection_creates_multiple_saved_variants(self):
        result = create_collection(self.db, "Orbit Collection", "A planetary series",
                                   ["orbit", "badge", "geometric"], "ocean")
        self.assertEqual(result["collection"]["data"]["variant_count"], 3)
        self.assertEqual(len(list_assets(self.db)), 3)
        with self.assertRaises(ValueError):
            create_collection(self.db, "Bad", "Repeated", ["orbit", "orbit"])

    def test_competitor_analysis_is_currency_matched_and_explained(self):
        result = analyze_competition([
            {"url":"https://shop.example/a","title":"A","price":20,"currency":"USD","reviews":100,"availability":"in stock","collected_at":"2026-11-05T10:00:00Z"},
            {"url":"https://shop.example/b","title":"B","price":30,"currency":"USD","reviews":50,"availability":"unknown","collected_at":"2026-11-05T10:00:00Z"},
        ])
        self.assertEqual(result["price_median"], 25)
        self.assertEqual(result["observation_count"], 2)
        with self.assertRaises(ValueError):
            analyze_competition([
                {"url":"https://shop.example/a","price":20,"currency":"USD","collected_at":"2026-11-05T10:00:00Z"},
                {"url":"https://shop.example/b","price":30,"currency":"INR","collected_at":"2026-11-05T10:00:00Z"},
            ])

    def test_pricing_scenarios_and_break_even(self):
        offer = Offer("POD", 30, 10, shipping_cost=4, platform_fee_rate=.05, payment_fee_rate=.03, currency="USD")
        result = pricing_scenarios(offer, [20, 30, 40], .25)
        self.assertEqual(len(result["scenarios"]), 3)
        self.assertGreater(result["target_price"], 0)
        taxed = Offer("POD", 100, 20, duty_cost=5, tax_rate=.1, return_rate=.05, chargeback_rate=.01)
        priced = pricing_scenarios(taxed, [100], .2)["scenarios"][0]
        self.assertEqual(priced["estimated_tax"], 10)
        self.assertEqual(priced["return_reserve"], 5)
        self.assertEqual(priced["chargeback_reserve"], 1)
        with self.assertRaises(ValueError):
            Offer("POD", 100, 20, tax_rate=1.5).validate()
        self.assertEqual(break_even_orders(100, 25)["orders"], 4)
        with self.assertRaises(ValueError):
            break_even_orders(100, 0)

    def test_period_pnl_keeps_currencies_separate_and_actual_estimate_distinct(self):
        add_finance_entry(self.db, "revenue", 100, "INR", "Sale", actual=True)
        add_finance_entry(self.db, "supplier_cost", 30, "INR", "Estimate", actual=False)
        add_finance_entry(self.db, "revenue", 10, "USD", "Foreign sale", actual=True)
        result = profit_and_loss(self.db)
        self.assertEqual(result["currencies"]["INR"]["actual_net"], 100)
        self.assertEqual(result["currencies"]["INR"]["estimated_net"], -30)
        self.assertIn("USD", result["currencies"])
        daily = profit_and_loss(self.db, start="2026-11-05", end="2026-11-05")
        self.assertIn("INR", daily["currencies"])

    def test_dependency_agent_plan_executes_output_reference(self):
        tasks = [
            {"kind":"creative.generate","payload":{"title":"Orbit","concept":"Planets","style":"orbit","palette":"midnight"}},
            {"kind":"listing.draft","depends_on":[0],"payload":{
                "product":{"title":{"$from":0,"path":"result.record.title"},"features":"Original artwork"},
                "audience":"space fans","keywords":["space","planet"]}},
        ]
        plan = plan_run("Creative to listing", tasks)
        self.assertEqual(plan["tasks"][1]["depends_on"], [0])
        result = submit_plan(self.db, "Creative to listing", tasks, "dependency-plan")
        self.assertEqual(len(result["job_ids"]), 1)
        duplicate = submit_plan(self.db, "Creative to listing", tasks, "dependency-plan")
        self.assertTrue(duplicate["duplicate"])
        with self.assertRaises(ValueError):
            submit_plan(self.db, "Different plan", tasks, "dependency-plan")
        job = run_once(self.db)
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(len(job["result"]["result"]["steps"]), 2)
        self.assertEqual(list_jobs(self.db)[0]["status"], "succeeded")

    def test_worker_revalidates_raw_agent_job_payload(self):
        from aureon.worker import process_job
        with self.assertRaises(ValueError):
            process_job({"kind":"agent.run","payload":{"plan":{"name":"nested","tasks":[
                {"kind":"agent.run","payload":{"plan":{"name":"recursive","tasks":[]}}}
            ]}}}, self.db)

    def test_dependency_rejects_forward_and_undeclared_references(self):
        with self.assertRaises(ValueError):
            plan_run("Bad", [{"kind":"creative.generate","payload":{"title":"A","concept":"B","style":"orbit","palette":"mono"},
                              "depends_on":[1]}])
        with self.assertRaises(ValueError):
            plan_run("Bad", [{"kind":"creative.generate","payload":{"title":"A","concept":"B","style":"orbit","palette":"mono"}},
                              {"kind":"listing.draft","payload":{"product":{"title":"A"},"audience":"B","keywords":["x"],
                               "unused":{"$from":0,"path":"result.record.id"}}}])

if __name__ == "__main__":
    unittest.main()
