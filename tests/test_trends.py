import unittest
from aureon.trends import fetch_trending_searches


class TrendInputTests(unittest.TestCase):
    def test_rejects_invalid_country_code(self):
        with self.assertRaises(ValueError):
            fetch_trending_searches("India")

    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            fetch_trending_searches("IN", 0)


if __name__ == "__main__":
    unittest.main()
