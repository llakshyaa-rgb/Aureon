import os
import unittest
from unittest.mock import patch
from aureon.providers import shopify


class ShopifyProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AUREON_SHOPIFY_STORE": "sample-store",
            "AUREON_SHOPIFY_ACCESS_TOKEN": "test-token",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_health_reports_configured_without_claiming_connected(self):
        result = shopify.health()
        self.assertTrue(result["configured"])
        self.assertFalse(result["connected"])

    def test_missing_credentials_are_rejected(self):
        with patch.dict(os.environ, {
            "AUREON_SHOPIFY_STORE": "",
            "AUREON_SHOPIFY_ACCESS_TOKEN": "",
        }):
            with self.assertRaises(RuntimeError):
                shopify.shop_info()

    def test_product_limit_is_validated(self):
        with self.assertRaises(ValueError):
            shopify.products(0)

    def test_draft_creation_sends_draft_status(self):
        with patch.object(shopify, "graphql", return_value={
            "productCreate": {"product": {
                "id": "gid://shopify/Product/1", "title": "Test", "status": "DRAFT"
            }, "userErrors": []}
        }) as call:
            result = shopify.create_draft_product(
                "Test", "A <safe> description", tags=["one", "two"])
        self.assertEqual(result["status"], "DRAFT")
        variables = call.call_args.args[1]
        self.assertEqual(variables["product"]["status"], "DRAFT")
        self.assertIn("&lt;safe&gt;", variables["product"]["descriptionHtml"])

    def test_draft_creation_rejects_empty_title(self):
        with self.assertRaises(ValueError):
            shopify.create_draft_product(" ")

    def test_shop_domain_is_validated(self):
        with patch.dict(os.environ, {
            "AUREON_SHOPIFY_STORE": "not a domain",
            "AUREON_SHOPIFY_ACCESS_TOKEN": "test-token",
        }):
            with self.assertRaises(ValueError):
                shopify.health()


if __name__ == "__main__":
    unittest.main()
