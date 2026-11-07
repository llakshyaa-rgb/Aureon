import unittest
from unittest.mock import patch

from aureon.trends import fetch_keyword_news


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

    def test_keyword_news_rejects_empty_or_invalid_queries(self):
        with self.assertRaises(ValueError):
            fetch_keyword_news([], "IN", 10)
        with self.assertRaises(ValueError):
            fetch_keyword_news([""], "IN", 10)
        with self.assertRaises(ValueError):
            fetch_keyword_news(["valid"], "IND", 10)


if __name__ == "__main__":
    unittest.main()
