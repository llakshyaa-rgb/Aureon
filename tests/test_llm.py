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
        self.assertNotIn("api_key_hint", again)
        self.assertNotIn("secret-test-key", json.dumps(again))

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

    def test_anthropic_native_messages_api(self):
        save_settings(self.db, {"provider": "anthropic", "model": "claude-test",
            "api_key": "anthropic-secret", "temperature": 0.2, "max_tokens": 512})
        with patch("aureon.llm._request_json", return_value={
            "content": [{"type": "text", "text": "AUREON CONNECTION OK"}]}) as request:
            result = generate(self.db, "system", "prompt")
        self.assertEqual(result["content"], "AUREON CONNECTION OK")
        self.assertTrue(request.call_args.args[0].endswith("/messages"))
        self.assertEqual(request.call_args.args[2]["x-api-key"], "anthropic-secret")

    def test_gemini_native_generate_content_api(self):
        save_settings(self.db, {"provider": "gemini", "model": "gemini-test",
            "api_key": "gemini-secret", "temperature": 0.2, "max_tokens": 512})
        with patch("aureon.llm._request_json", return_value={
            "candidates": [{"content": {"parts": [{"text": "AUREON CONNECTION OK"}]}}]}) as request:
            result = generate(self.db, "system", "prompt")
        self.assertEqual(result["content"], "AUREON CONNECTION OK")
        self.assertIn("/models/gemini-test:generateContent", request.call_args.args[0])
        self.assertIn("gemini-secret", request.call_args.args[0])

    def test_openrouter_retries_a_short_non_answer_for_json_chat(self):
        save_settings(self.db, {"provider": "openrouter", "model": "",
            "api_key": "openrouter-secret", "temperature": 0.2, "max_tokens": 512})
        candidates = [{"id": "free/model-one"}, {"id": "free/model-two"}]
        first = {"choices": [{"message": {"content": '{"reply":"interests","tasks":[],"needs_input":""}'}}]}
        second = {"choices": [{"message": {"content": '{"reply":"I will research the product opportunity and prepare the requested launch plan.","tasks":[],"needs_input":""}'}}]}
        with patch("aureon.llm._select_openrouter_models", return_value=candidates), \
             patch("aureon.llm._request_json", side_effect=[first, second]) as request:
            result = generate(self.db, "system", "A" * 800, json_mode=True)
        self.assertEqual(result["model"], "free/model-two")
        self.assertIn("research the product opportunity", result["content"])
        self.assertEqual(request.call_count, 2)

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
