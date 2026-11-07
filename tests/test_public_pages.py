import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aureon.db import initialize
from aureon.workflows import initialize_workspace, list_records
from aureon.public_pages import parse_product_page, _validate_public_url, research_public_product_page


class PublicProductPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "aureon.sqlite3"
        initialize(self.db)
        initialize_workspace(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_extracts_jsonld_product_price_currency_and_brand(self):
        html = """<html><head><title>Store</title>
        <script type="application/ld+json">{"@type":"Product","name":"Steel Bottle",
        "brand":{"@type":"Brand","name":"Example"},"offers":{"@type":"Offer",
        "price":"799.00","priceCurrency":"INR","availability":"https://schema.org/InStock"}}</script>
        </head></html>"""
        result = parse_product_page(html, "https://shop.example/product")
        self.assertEqual(result["title"], "Steel Bottle")
        self.assertEqual(result["price"], 799.0)
        self.assertEqual(result["currency"], "INR")
        self.assertEqual(result["brand"], "Example")
        self.assertTrue(result["price_found"])

    def test_extracts_open_graph_title_and_meta_price(self):
        html = '<meta property="og:title" content="Canvas Tote"><meta property="product:price:amount" content="12.50"><meta property="product:price:currency" content="USD">'
        result = parse_product_page(html, "https://shop.example/tote")
        self.assertEqual(result["title"], "Canvas Tote")
        self.assertEqual(result["price"], 12.5)
        self.assertEqual(result["currency"], "USD")

    def test_rejects_non_https_and_private_network_urls(self):
        with self.assertRaises(ValueError):
            _validate_public_url("http://example.com/product")
        with patch("aureon.public_pages.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                _validate_public_url("https://example.com/product")

    def test_persists_observation_with_source_and_timestamp(self):
        html = '<title>Example Hoodie</title><meta property="product:price:amount" content="1499"><meta property="product:price:currency" content="INR">'
        with patch("aureon.public_pages.fetch_product_page", return_value={
            "title": "Example Hoodie", "price": 1499.0, "currency": "INR",
            "availability": None, "brand": None, "source_url": "https://shop.example/hoodie",
            "price_found": True, "evidence_type": "public_product_page_observation"}):
            result = research_public_product_page(self.db, "https://shop.example/hoodie")
        self.assertEqual(result["observation"]["price"], 1499.0)
        records = list_records(self.db, "opportunity")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["data"]["competitor_observation"]["currency"], "INR")
        self.assertEqual(records[0]["data"]["research_status"], "unverified_public_listing_observation")


if __name__ == "__main__":
    unittest.main()
