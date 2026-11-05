import os
import unittest
from unittest.mock import patch
from aureon.providers import printify


class PrintifyProviderTests(unittest.TestCase):
    def test_health_is_disconnected_without_token(self):
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": ""}):
            self.assertFalse(printify.health()["configured"])

    def test_catalog_path_validation(self):
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": "token"}):
            with self.assertRaises(ValueError):
                printify.blueprint("../secret")

    def test_product_creation_validates_required_fields(self):
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": "token"}):
            with self.assertRaises(ValueError):
                printify.create_product(123, {"title": "Incomplete"})

    def test_artwork_upload_requires_https(self):
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": "token"}):
            with self.assertRaises(ValueError):
                printify.upload_image_url("art.png", "http://example.com/art.png")

    def test_product_payload_is_normalized_and_hidden(self):
        product = {
            "title": " Test shirt ",
            "blueprint_id": "384",
            "print_provider_id": "1",
            "variants": [{"id": "45740", "price": 1200, "is_enabled": True}],
            "print_areas": [{
                "variant_ids": [45740],
                "placeholders": [{
                    "position": "front",
                    "decoration_method": "dtg",
                    "images": [{"id": "uploaded-image-id", "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}],
                }],
            }],
            "visible": True,
        }
        shop_id, payload = printify.validate_product("12", product)
        self.assertEqual(shop_id, 12)
        self.assertEqual(payload["title"], "Test shirt")
        self.assertIs(payload["visible"], False)
        self.assertEqual(payload["variants"][0]["id"], 45740)

    def test_create_product_forces_hidden_visibility(self):
        product = {
            "title": "Test",
            "blueprint_id": 384,
            "print_provider_id": 1,
            "variants": [{"id": 45740, "price": 1200, "is_enabled": True}],
            "print_areas": [{
                "variant_ids": [45740],
                "placeholders": [{
                    "position": "front", "decoration_method": "dtg",
                    "images": [{"id": "uploaded-image-id"}],
                }],
            }],
            "visible": True,
        }
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": "token"}):
            with patch.object(printify, "request", return_value={"id": "product-1", "visible": False}) as call:
                result = printify.create_product(12, product)
        self.assertFalse(result["visible"])
        self.assertFalse(call.call_args.kwargs["body"]["visible"])

    def test_print_area_cannot_reference_unknown_variant(self):
        product = {
            "title": "Test",
            "blueprint_id": 384,
            "print_provider_id": 1,
            "variants": [{"id": 45740, "price": 1200, "is_enabled": True}],
            "print_areas": [{
                "variant_ids": [99999],
                "placeholders": [{
                    "position": "front", "decoration_method": "dtg",
                    "images": [{"id": "uploaded-image-id"}],
                }],
            }],
        }
        with self.assertRaises(ValueError):
            printify.validate_product(12, product)

    def test_upload_rejects_single_backslash_filename(self):
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": "token"}):
            with self.assertRaises(ValueError):
                printify.upload_image_url("folder" + chr(92) + "art.png", "https://example.com/art.png")

    def test_missing_token_is_rejected(self):
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                printify.shops()


if __name__ == "__main__":
    unittest.main()
