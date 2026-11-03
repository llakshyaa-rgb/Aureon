import tempfile
import unittest
from pathlib import Path

from aureon.db import initialize
from aureon.jobs import claim_next, enqueue, fail, finish, list_jobs


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

    def test_empty_queue(self):
        self.assertIsNone(claim_next(self.db))


if __name__ == "__main__":
    unittest.main()
