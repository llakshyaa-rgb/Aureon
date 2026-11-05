import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aureon.db import initialize
from aureon.workflows import initialize_workspace, list_records
from aureon.trends import collect_trends, trend_history


class TrendCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "aureon.sqlite3"
        initialize(self.db)
        initialize_workspace(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_persists_and_deduplicates_trends(self):
        sample = {
            "provider": "Google Trends public Trending RSS",
            "geo": "IN",
            "fetched_at": "2026-11-05T12:00:00+00:00",
            "count": 1,
            "items": [{
                "title": "Example search",
                "traffic": "10K+",
                "published_at": "Thu, 05 Nov 2026 11:00:00 GMT",
                "link": "https://trends.google.com/trending/explore?geo=IN",
                "news": [],
            }],
        }
        with patch("aureon.trends.fetch_trending_searches", return_value=sample):
            first = collect_trends(self.db, "IN")
            second = collect_trends(self.db, "IN")
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        rows = list_records(self.db, "opportunity")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data"]["trend_geo"], "IN")
        history = trend_history(self.db, "IN")
        self.assertEqual(history["snapshot_count"], 2)
        self.assertEqual(history["rank_movement"]["Example search"]["direction"], "steady")


if __name__ == "__main__":
    unittest.main()
