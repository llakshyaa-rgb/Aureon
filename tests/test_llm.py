import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aureon.llm import save_settings, public_settings, generate, PROVIDERS


class LLMSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "data" / "aureon.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_all_provider_presets_are_exposed(self):
        public = public_settings(self.db)
        ids = {item["id"] for item in public["providers"]}
        self.assertTrue({"openai", "anthropic", "gemini", "openrouter",
                         "groq", "deepseek", "mistral", "ollama", "lm_studio", "nvidia", "sambanova", "siliconflow", "custom"}.issubset(ids))

    def test_key_is_never_returned_and_blank_preserves_existing(self):
        saved = save_settings(self.db, {
            "provider": "openrouter", "model": "provider/model-id",
            "api_key": "secret-test-key", "temperature": 0.2, "max_tokens": 1024})
        self.assertTrue(saved["api_key_set"])
        self.assertNotIn("secret-test-key", json.dumps(saved))
        again = save_settings(self.db, {
            "provider": "openrouter", "model": "provider/model-id",
            "api_key": "", "temperature": 0.2, "max_tokens": 1024})
        self.assertTrue(again["api_key_set"])
        self.assertTrue(again["api_key_hint"].endswith("t-key"))

    def test_rejects_insecure_cloud_endpoint_and_invalid_model(self):
        with self.assertRaises(ValueError):
            save_settings(self.db, {"provider": "openai", "base_url": "http://example.com/v1",
                                    "model": "x", "api_key": "secret"})
        with self.assertRaises(ValueError):
            save_settings(self.db, {"provider": "openai", "model": "",
                                    "api_key": "secret"})

    def test_local_lm_studio_accepts_loopback_without_api_key(self):
        saved = save_settings(self.db, {"provider": "lm_studio",
            "base_url": "http://127.0.0.1:1234/v1", "model": "loaded-model",
            "api_key": "", "temperature": 0.1, "max_tokens": 512})
        self.assertEqual(saved["provider"], "lm_studio")
        self.assertFalse(saved["api_key_set"])

    def test_switching_provider_does_not_reuse_another_providers_key(self):
        save_settings(self.db, {"provider": "openai", "model": "gpt-model",
            "api_key": "openai-secret", "temperature": 0.2, "max_tokens": 512})
        with self.assertRaises(ValueError):
            save_settings(self.db, {"provider": "anthropic", "model": "claude-model",
                "api_key": "", "temperature": 0.2, "max_tokens": 512})

    def test_ollama_accepts_loopback_without_api_key(self):
        saved = save_settings(self.db, {"provider": "ollama",
            "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:3b",
            "api_key": "", "temperature": 0.1, "max_tokens": 512})
        self.assertEqual(saved["provider"], "ollama")
        self.assertFalse(saved["api_key_set"])

    def test_openai_compatible_generation_uses_configured_model(self):
        save_settings(self.db, {"provider": "deepseek", "model": "deepseek-chat",
            "api_key": "secret", "temperature": 0.2, "max_tokens": 512})
        with patch("aureon.llm._request_json", return_value={
            "choices": [{"message": {"content": "AUREON CONNECTION OK"}}]}) as request:
            result = generate(self.db, "system", "prompt")
        self.assertEqual(result["content"], "AUREON CONNECTION OK")
        self.assertEqual(result["model"], "deepseek-chat")
        self.assertIn("api.deepseek.com", request.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
