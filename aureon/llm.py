"""Provider-neutral LLM settings and inference for Aureon.

Secrets are stored in a local JSON file beside the SQLite database with owner-only
permissions where supported. The HTTP API never returns the secret.
"""
import json
import re
import time
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, quote
from urllib.error import HTTPError, URLError

PROVIDERS = {
    "openai": {"label": "OpenAI", "protocol": "openai", "base_url": "https://api.openai.com/v1", "models": "Enter any model ID supported by your account"},
    "anthropic": {"label": "Anthropic", "protocol": "anthropic", "base_url": "https://api.anthropic.com/v1", "models": "Claude model ID"},
    "gemini": {"label": "Google Gemini", "protocol": "gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta", "models": "Gemini model ID, e.g. gemini-2.5-flash"},
    "openrouter": {"label": "OpenRouter", "protocol": "openai", "base_url": "https://openrouter.ai/api/v1", "models": "Any model slug available in your OpenRouter account"},
    "apinex": {"label": "APInex", "protocol": "openai", "base_url": "https://api.apinex.bond/v1", "models": "Free DeepSeek model: free/deepseek-v4.1-flash (or another exact APInex model ID)"},
    "groq": {"label": "Groq", "protocol": "openai", "base_url": "https://api.groq.com/openai/v1", "models": "Any Groq-supported model ID"},
    "together": {"label": "Together AI", "protocol": "openai", "base_url": "https://api.together.xyz/v1", "models": "Any Together model ID"},
    "deepseek": {"label": "DeepSeek", "protocol": "openai", "base_url": "https://api.deepseek.com/v1", "models": "Any DeepSeek model ID"},
    "mistral": {"label": "Mistral", "protocol": "openai", "base_url": "https://api.mistral.ai/v1", "models": "Any Mistral model ID"},
    "cerebras": {"label": "Cerebras", "protocol": "openai", "base_url": "https://api.cerebras.ai/v1", "models": "Any Cerebras-supported model ID"},
    "xai": {"label": "xAI", "protocol": "openai", "base_url": "https://api.x.ai/v1", "models": "Any xAI model ID"},
    "fireworks": {"label": "Fireworks AI", "protocol": "openai", "base_url": "https://api.fireworks.ai/inference/v1", "models": "Any Fireworks model ID"},
    "perplexity": {"label": "Perplexity", "protocol": "openai", "base_url": "https://api.perplexity.ai", "models": "Any Perplexity model ID"},
    "ollama": {"label": "Ollama (local)", "protocol": "openai", "base_url": "http://127.0.0.1:11434/v1", "models": "Exact locally installed Ollama model tag; no API key needed"},
    "lm_studio": {"label": "LM Studio (local)", "protocol": "openai", "base_url": "http://127.0.0.1:1234/v1", "models": "Exact model identifier loaded in LM Studio"},
    "nvidia": {"label": "NVIDIA NIM", "protocol": "openai", "base_url": "https://integrate.api.nvidia.com/v1", "models": "Any model deployed in NVIDIA NIM"},
    "sambanova": {"label": "SambaNova", "protocol": "openai", "base_url": "https://api.sambanova.ai/v1", "models": "Any SambaNova-supported model ID"},
    "siliconflow": {"label": "SiliconFlow", "protocol": "openai", "base_url": "https://api.siliconflow.com/v1", "models": "Any SiliconFlow model ID"},
    "custom": {"label": "Custom OpenAI-compatible endpoint", "protocol": "openai", "base_url": "", "models": "Any model ID exposed by your endpoint"},
}


def _settings_path(db_path):
    return Path(db_path).expanduser().resolve().parent / "llm_settings.json"


def load_settings(db_path):
    path = _settings_path(db_path)
    if not path.is_file():
        return {"provider": "openrouter", "base_url": PROVIDERS["openrouter"]["base_url"],
                "model": "", "api_key": "", "temperature": 0.2, "max_tokens": 1800}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RuntimeError("LLM settings file is unreadable; open Settings and save it again.")
    if not isinstance(data, dict):
        raise RuntimeError("LLM settings file has an invalid format.")
    return data


def public_settings(db_path):
    data = load_settings(db_path)
    provider = data.get("provider", "custom")
    info = PROVIDERS.get(provider, PROVIDERS["custom"])
    return {
        "providers": [{"id": key, "label": value["label"], "protocol": value["protocol"],
                       "base_url": value["base_url"], "models": value["models"]}
                      for key, value in PROVIDERS.items()],
        "provider": provider, "base_url": data.get("base_url", info["base_url"]),
        "model": data.get("model", ""), "api_key_set": bool(data.get("api_key")),
        
        "temperature": data.get("temperature", 0.2),
        "max_tokens": data.get("max_tokens", 1800),
    }



_OPENROUTER_CACHE = {"at": 0.0, "models": []}

def _openrouter_free_models(key):
    now = time.time()
    if _OPENROUTER_CACHE["models"] and now - _OPENROUTER_CACHE["at"] < 900:
        return list(_OPENROUTER_CACHE["models"])
    req = Request("https://openrouter.ai/api/v1/models", headers={"Authorization": "Bearer " + key, "Accept": "application/json", "User-Agent": "Aureon/1.0"})
    try:
        with urlopen(req, timeout=25) as response:
            payload = json.loads(response.read(5000000).decode("utf-8"))
    except Exception as exc:
        if _OPENROUTER_CACHE["models"]:
            return list(_OPENROUTER_CACHE["models"])
        raise RuntimeError("Could not load OpenRouter model catalogue: " + str(exc)) from None
    models = []
    for item in payload.get("data", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        pricing = item.get("pricing") or {}
        try:
            free = float(pricing.get("prompt", -1)) == 0 and float(pricing.get("completion", -1)) == 0
        except (TypeError, ValueError):
            free = False
        modalities = (item.get("architecture") or {}).get("output_modalities", ["text"])
        if (free or item["id"].endswith(":free")) and "text" in modalities:
            models.append(item)
    if not models:
        raise RuntimeError("OpenRouter returned no eligible free text models.")
    _OPENROUTER_CACHE.update({"at": now, "models": models})
    return list(models)

def _model_size(item):
    value = (item.get("id", "") + " " + item.get("name", "")).lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*([bm])", value)
    if not match:
        return 8.0
    return float(match.group(1)) * (1000 if match.group(2) == "b" else 1)

def _select_openrouter_models(key, system, prompt):
    models = _openrouter_free_models(key)
    # Rank the user's actual request, not Aureon's system instructions.
    task = str(prompt).lower()
    hard = ("research", "analyze", "strategy", "compare", "forecast", "debug", "multi-step", "comprehensive", "evaluate", "calculate")
    easy = ("hello", "hi ", "thanks", "rewrite", "shorten", "simple", "define", "summarize")
    if len(prompt) > 4000 or any(word in task for word in hard):
        models.sort(key=lambda item: (-_model_size(item), -int(item.get("context_length") or 0)))
    elif len(prompt) < 500 or any(word in task for word in easy):
        models.sort(key=lambda item: (_model_size(item), -int(item.get("context_length") or 0)))
    else:
        models.sort(key=lambda item: (abs(_model_size(item) - 8), -int(item.get("context_length") or 0)))
    return models[:12]

def save_settings(db_path, body):
    if not isinstance(body, dict):
        raise ValueError("settings must be an object")
    provider = str(body.get("provider", "")).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("Choose a supported provider or Custom endpoint.")
    info = PROVIDERS[provider]
    base_url = str(body.get("base_url") or info["base_url"]).strip().rstrip("/")
    model = str(body.get("model") or "").strip()
    previous = load_settings(db_path)
    key = body.get("api_key")
    if key is None or key == "":
        key = previous.get("api_key", "") if previous.get("provider") == provider else ""
    if not isinstance(key, str) or len(key) > 4096:
        raise ValueError("API key must be text shorter than 4096 characters.")
    if (provider != "openrouter" and not model) or len(model) > 240:
        raise ValueError("Enter the exact model ID supplied by your provider.")
    if not base_url or len(base_url) > 500:
        raise ValueError("Base URL is required.")
    local_providers = {"ollama", "lm_studio"}
    parsed_url = urlsplit(base_url)
    is_loopback = parsed_url.scheme == "http" and parsed_url.hostname in {"127.0.0.1", "localhost", "::1"}
    if provider in local_providers:
        if not is_loopback:
            raise ValueError("Local model providers must use a loopback URL.")
    elif provider == "custom" and parsed_url.scheme == "http":
        if not is_loopback:
            raise ValueError("Custom HTTP endpoints are allowed only on localhost; cloud endpoints must use HTTPS.")
    elif not base_url.startswith("https://"):
        raise ValueError("Cloud provider endpoints must use HTTPS.")
    try:
        temperature = float(body.get("temperature", 0.2))
        max_tokens = int(body.get("max_tokens", 1800))
    except (TypeError, ValueError):
        raise ValueError("Temperature and maximum tokens must be numeric.") from None
    if not 0 <= temperature <= 2 or not 128 <= max_tokens <= 8192:
        raise ValueError("Temperature must be 0–2 and max tokens 128–8192.")
    if provider not in {"ollama", "lm_studio"} and not key:
        raise ValueError("An API key is required for this provider.")
    data = {"provider": provider, "base_url": base_url, "model": model,
            "api_key": key, "temperature": temperature, "max_tokens": max_tokens}
    path = _settings_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".llm-", suffix=".tmp", dir=str(path.parent))
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return public_settings(db_path)


def _request_json(url, payload, headers, timeout=60):
    req = Request(url, data=json.dumps(payload).encode("utf-8"),
                  headers={**headers, "Content-Type": "application/json"},
                  method="POST")
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(2_000_000)
        return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read(4000).decode("utf-8", "replace")
        raise RuntimeError("LLM provider HTTP " + str(exc.code) + ": " + detail[:1200]) from None
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("LLM provider connection failed: " + str(exc)) from None
    except json.JSONDecodeError:
        raise RuntimeError("LLM provider returned invalid JSON.") from None


def generate(db_path, system, prompt, json_mode=False):
    data = load_settings(db_path)
    provider = data.get("provider", "")
    info = PROVIDERS.get(provider)
    if not info:
        raise RuntimeError("Choose an LLM provider in Aureon Settings first.")
    model = data.get("model", "")
    key = data.get("api_key", "")
    base = data.get("base_url", info["base_url"]).rstrip("/")
    candidates = []
    if provider == "openrouter":
        if not key:
            raise RuntimeError("OpenRouter API key is missing.")
        candidates = _select_openrouter_models(key, system, prompt)
        model = candidates[0]["id"]
    elif not model:
        raise RuntimeError("Set a model ID in Aureon Settings first.")
    protocol = info["protocol"]
    if protocol == "anthropic":
        if not key:
            raise RuntimeError("Anthropic API key is missing.")
        result = _request_json(base + "/messages", {
            "model": model, "max_tokens": data.get("max_tokens", 1800),
            "temperature": data.get("temperature", 0.2),
            "system": system, "messages": [{"role": "user", "content": prompt}],
        }, {"x-api-key": key, "anthropic-version": "2023-06-01"})
        content = "".join(x.get("text", "") for x in result.get("content", []) if x.get("type") == "text")
    elif protocol == "gemini":
        if not key:
            raise RuntimeError("Gemini API key is missing.")
        result = _request_json(base + "/models/" + quote(model, safe="") + ":generateContent?key=" + quote(key, safe=""), {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": data.get("temperature", 0.2),
                                 "maxOutputTokens": data.get("max_tokens", 1800),
                                 **({"responseMimeType": "application/json"} if json_mode else {})},
        }, {})
        content = "".join(p.get("text", "") for p in result.get("candidates", [{}])[0].get("content", {}).get("parts", []))
    else:
        if provider not in {"ollama", "lm_studio"} and not key:
            raise RuntimeError("Provider API key is missing.")
        payload = {"model": model, "temperature": data.get("temperature", 0.2),
                   "max_tokens": data.get("max_tokens", 1800),
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": prompt}]}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": "Bearer " + key} if key else {}
        if provider == "openrouter":
            failures = []
            content = ""
            selected_model = ""
            # Free routes can intermittently return HTTP 200 with an empty
            # message. Retry that route once with a smaller output budget,
            # then move on to another free model.
            for candidate in candidates[:12]:
                model = candidate["id"]
                payload["model"] = model
                model_error = None
                for attempt in range(2):
                    attempt_payload = dict(payload)
                    if attempt:
                        attempt_payload["max_tokens"] = min(int(payload.get("max_tokens", 1800)), 1200)
                        attempt_payload["temperature"] = 0.1
                    try:
                        result = _request_json(base + "/chat/completions", attempt_payload, headers)
                        choices = result.get("choices") if isinstance(result, dict) else None
                        choice = choices[0] if isinstance(choices, list) and choices else {}
                        message = choice.get("message") if isinstance(choice, dict) else {}
                        message = message if isinstance(message, dict) else {}
                        candidate_content = message.get("content", "")
                        if isinstance(candidate_content, list):
                            candidate_content = "".join(
                                part.get("text", "") for part in candidate_content
                                if isinstance(part, dict) and isinstance(part.get("text"), str)
                            )
                        if isinstance(candidate_content, str) and candidate_content.strip():
                            if json_mode:
                                candidate_text = candidate_content.strip()
                                if candidate_text.startswith("```"):
                                    candidate_text = candidate_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                                try:
                                    parsed = json.loads(candidate_text)
                                except (TypeError, json.JSONDecodeError):
                                    parsed = None
                                if not isinstance(parsed, dict):
                                    model_error = "malformed JSON"
                                    # This model produced text, but not a usable
                                    # structured answer. Move to the next model
                                    # rather than spending another retry on it.
                                    break
                                if len(prompt) > 700 and not parsed.get("tasks") and len(str(parsed.get("reply", "")).strip()) < 40 and len(str(parsed.get("needs_input", "")).strip()) < 20:
                                    model_error = "incomplete answer"
                                    break
                            content = candidate_content
                            selected_model = model
                            break
                        finish = choice.get("finish_reason") if isinstance(choice, dict) else None
                        model_error = "empty response" + ((" (finish reason: " + str(finish) + ")") if finish else "")
                    except RuntimeError as exc:
                        model_error = str(exc)[:240]
                    if attempt == 0:
                        continue
                if content:
                    break
                failures.append(model + ": " + (model_error or "no text returned"))
            if not content:
                details = "; ".join(failures[-4:])
                raise RuntimeError(
                    "OpenRouter's free models are not returning usable text right now. "
                    "Aureon tried up to 12 models (with one retry each). "
                    "This is a model-route availability issue, not a problem with your prompt. "
                    "Last errors: " + details
                )
            model = selected_model
        else:
            result = _request_json(base + "/chat/completions", payload, headers)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM provider returned an empty response.")
    return {"provider": provider, "model": model, "content": content.strip()}


def test_connection(db_path):
    result = generate(db_path, "You are a connection test. Be concise.",
                      "Reply with exactly: AUREON CONNECTION OK", False)
    return {"ok": True, "provider": result["provider"], "model": result["model"],
            "response": result["content"][:300]}


def clear_settings(db_path):
    """Remove the saved provider, model and API key from this device."""
    path = _settings_path(db_path)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError("Could not remove saved model settings: " + str(exc)) from None
    return {"cleared": True, **public_settings(db_path)}
