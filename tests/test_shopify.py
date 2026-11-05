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
        with patch.object(shopify, "graphql", side_effect=[
            {"productCreate": {"product": {
                "id": "gid://shopify/Product/1", "title": "Test", "status": "DRAFT",
                "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/1"}]}
            }, "userErrors": []}},
            {"productVariantsBulkUpdate": {
                "productVariants": [{"id": "gid://shopify/ProductVariant/1", "price": "12.50"}],
                "userErrors": []
            }},
        ]) as call:
            result = shopify.create_draft_product(
                "Test", 12.5, "A <safe> description", tags=["one", "two"])
        self.assertEqual(result["status"], "DRAFT")
        self.assertEqual(result["variant_price"], "12.50")
        variables = call.call_args_list[0].args[1]
        self.assertEqual(variables["product"]["status"], "DRAFT")
        self.assertIn("&lt;safe&gt;", variables["product"]["descriptionHtml"])
        self.assertEqual(call.call_args_list[1].args[1]["variants"][0]["price"], "12.50")

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
