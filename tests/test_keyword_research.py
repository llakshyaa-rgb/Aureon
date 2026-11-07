import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aureon.db import initialize
from aureon.workflows import initialize_workspace, list_records
from aureon.trends import collect_keyword_research, fetch_keyword_news


class _FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.payload[:limit]


class KeywordNewsResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "aureon.sqlite3"
        initialize(self.db)
        initialize_workspace(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_keyword_news_keeps_source_date_and_deduplicates_urls(self):
        xml = b"""<rss><channel>
          <item><title>Reusable bottle market update</title>
          <link>https://news.google.com/articles/example-one</link>
          <pubDate>Sat, 07 Nov 2026 10:00:00 GMT</pubDate>
          <source>Example News</source></item>
        </channel></rss>"""
        with patch("aureon.trends.urlopen", side_effect=lambda *a, **k: _FakeResponse(xml)) as request:
            result = fetch_keyword_news(["reusable bottle", "steel bottle"], "IN", 10)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["source"], "Example News")
        self.assertEqual(result["items"][0]["published_at"], "Sat, 07 Nov 2026 10:00:00 GMT")
        self.assertIn("q=reusable+bottle", request.call_args_list[0].args[0].full_url)
        self.assertTrue(result["limitations"])

    def test_keyword_research_persists_cited_opportunities_once(self):
        xml = b"""<rss><channel>
          <item><title>Reusable bottle market update</title>
          <link>https://news.google.com/articles/example-one</link>
          <pubDate>Sat, 07 Nov 2026 10:00:00 GMT</pubDate>
          <source>Example News</source></item>
        </channel></rss>"""
        with patch("aureon.trends.urlopen", side_effect=lambda *a, **k: _FakeResponse(xml)):
            first = collect_keyword_research(self.db, ["reusable bottle"], "IN", 10)
        with patch("aureon.trends.urlopen", side_effect=lambda *a, **k: _FakeResponse(xml)):
            second = collect_keyword_research(self.db, ["reusable bottle"], "IN", 10)
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        records = list_records(self.db, "opportunity")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["data"]["evidence"][0]["source"], "Example News")
        self.assertEqual(records[0]["data"]["research_status"], "unvalidated_news_signal")

    def test_keyword_news_rejects_empty_or_invalid_queries(self):
        with self.assertRaises(ValueError):
            fetch_keyword_news([], "IN", 10)
        with self.assertRaises(ValueError):
            fetch_keyword_news([""], "IN", 10)
        with self.assertRaises(ValueError):
            fetch_keyword_news(["valid"], "IND", 10)


if __name__ == "__main__":
    unittest.main()
