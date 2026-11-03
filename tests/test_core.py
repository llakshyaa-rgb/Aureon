import tempfile
import unittest
from pathlib import Path
from aureon.db import initialize
from aureon.jobs import claim_next, enqueue, fail, finish, list_jobs, recover_interrupted
from aureon.intelligence.economics import Offer, calculate_unit_economics, compare_channels
from aureon.intelligence.scoring import score_opportunity

class JobQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.sqlite3"
        initialize(self.db)
    def tearDown(self):
        self.temp.cleanup()
    def test_enqueue_claim_finish(self):
        created = enqueue(self.db, "research.scan", {"query": "desk mats"})
        claimed = claim_next(self.db)
        self.assertEqual(created["id"], claimed["id"])
        self.assertEqual(claimed["status"], "running")
        finish(self.db, claimed["id"], {"signals": 3})
        self.assertEqual(list_jobs(self.db)[0]["status"], "succeeded")
    def test_idempotency_key(self):
        first = enqueue(self.db, "listing.draft", {}, "same-request")
        second = enqueue(self.db, "listing.draft", {"ignored": True}, "same-request")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(list_jobs(self.db)), 1)
    def test_retry_is_bounded(self):
        job = enqueue(self.db, "supplier.quote", {}, max_attempts=1)
        claim_next(self.db)
        fail(self.db, job["id"], "temporary failure")
        self.assertEqual(list_jobs(self.db)[0]["status"], "failed")
    def test_interrupted_job_is_requeued(self):
        enqueue(self.db, "research.scan", {}, max_attempts=3)
        claim_next(self.db)
        self.assertEqual(recover_interrupted(self.db), {"requeued": 1, "failed": 0})
        recovered = list_jobs(self.db)[0]
        self.assertEqual(recovered["status"], "queued")
        self.assertEqual(recovered["attempts"], 1)
    def test_interrupted_job_at_retry_limit_fails(self):
        enqueue(self.db, "research.scan", {}, max_attempts=1)
        claim_next(self.db)
        self.assertEqual(recover_interrupted(self.db), {"requeued": 0, "failed": 1})
        self.assertEqual(list_jobs(self.db)[0]["status"], "failed")
    def test_empty_queue(self):
        self.assertIsNone(claim_next(self.db))
    def test_invalid_payload_rejected(self):
        with self.assertRaises(ValueError):
            enqueue(self.db, "test", ["not", "an", "object"])

class EconomicsTests(unittest.TestCase):
    def test_unit_economics(self):
        offer = Offer("POD", 30, 12, 5, platform_fee_rate=0.05,
                      payment_fee_rate=0.03, payment_fixed_fee=0.30,
                      estimated_ad_cost=3, currency="USD")
        result = calculate_unit_economics(offer)
        self.assertEqual(result["total_cost"], 22.70)
        self.assertEqual(result["estimated_profit"], 7.30)
        self.assertAlmostEqual(result["profit_margin"], 7.3 / 30)
    def test_negative_profit_is_visible(self):
        result = calculate_unit_economics(Offer("dropshipping", 10, 8, 4))
        self.assertEqual(result["estimated_profit"], -2)
        self.assertFalse(result["profitable_before_ads"])
    def test_channel_comparison(self):
        pod = Offer("POD", 30, 12, 4, currency="USD")
        dropship = Offer("dropshipping", 30, 10, 8, currency="USD")
        self.assertEqual(compare_channels(pod, dropship)["recommended_channel"], "POD")
    def test_currency_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            compare_channels(Offer("POD", 20, 8, currency="USD"),
                             Offer("dropship", 20, 8, currency="INR"))
    def test_invalid_fee_rejected(self):
        with self.assertRaises(ValueError):
            calculate_unit_economics(Offer("POD", 20, 8, platform_fee_rate=1.2))

class OpportunityScoringTests(unittest.TestCase):
    def test_score_and_tier(self):
        result = score_opportunity({"demand": 80, "trend": 75, "margin": 70,
                                    "competition": 60, "shipping": 90, "confidence": 85})
        self.assertEqual(result["score"], 74.25)
        self.assertEqual(result["tier"], "investigate")
    def test_missing_signal_rejected(self):
        with self.assertRaises(ValueError):
            score_opportunity({"demand": 80})
    def test_out_of_range_signal_rejected(self):
        with self.assertRaises(ValueError):
            score_opportunity({"demand": 101, "trend": 75, "margin": 70,
                               "competition": 60, "shipping": 90, "confidence": 85})

if __name__ == "__main__":
    unittest.main()
