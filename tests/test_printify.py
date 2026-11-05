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

    def test_missing_token_is_rejected(self):
        with patch.dict(os.environ, {"AUREON_PRINTIFY_API_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                printify.shops()


if __name__ == "__main__":
    unittest.main()
