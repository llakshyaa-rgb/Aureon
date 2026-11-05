"""Printify read-only shop and catalog discovery."""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://api.printify.com/v1"


def health():
    token = os.getenv("AUREON_PRINTIFY_API_TOKEN", "").strip()
    return {"name": "Printify", "configured": bool(token),
            "mode": "credentials_configured" if token else "disconnected"}


def request(path):
    token = os.getenv("AUREON_PRINTIFY_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Printify token is not configured.")
    if not path.startswith("/") or ".." in path or "#" in path:
        raise ValueError("invalid Printify API path")
    req = Request(BASE + path, headers={
        "Authorization": "Bearer " + token,
        "User-Agent": "AureonCommerce/0.3",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=20) as response:
            return json.loads(response.read(4_000_000))
    except HTTPError as exc:
        raise RuntimeError("Printify HTTP " + str(exc.code) +
                           "; check token permissions and account.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not reach Printify; check network.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Printify returned invalid JSON.") from None


def shops():
    data = request("/shops.json")
    return data if isinstance(data, list) else []


def blueprints():
    data = request("/catalog/blueprints.json")
    return data if isinstance(data, list) else []


def blueprint(blueprint_id):
    if isinstance(blueprint_id, bool) or not str(blueprint_id).isdigit():
        raise ValueError("blueprint_id must be numeric")
    return request("/catalog/blueprints/" + str(int(blueprint_id)) + ".json")


def print_providers(blueprint_id):
    if isinstance(blueprint_id, bool) or not str(blueprint_id).isdigit():
        raise ValueError("blueprint_id must be numeric")
    data = request("/catalog/blueprints/" + str(int(blueprint_id)) + "/print_providers.json")
    return data if isinstance(data, list) else []


def variants(blueprint_id, provider_id, include_out_of_stock=False):
    if isinstance(blueprint_id, bool) or not str(blueprint_id).isdigit():
        raise ValueError("blueprint_id must be numeric")
    if isinstance(provider_id, bool) or not str(provider_id).isdigit():
        raise ValueError("provider_id must be numeric")
    suffix = "?show-out-of-stock=1" if include_out_of_stock else ""
    data = request("/catalog/blueprints/" + str(int(blueprint_id)) +
                   "/print_providers/" + str(int(provider_id)) + "/variants.json" + suffix)
    return data if isinstance(data, list) else []


def shipping(blueprint_id, provider_id):
    if isinstance(blueprint_id, bool) or not str(blueprint_id).isdigit():
        raise ValueError("blueprint_id must be numeric")
    if isinstance(provider_id, bool) or not str(provider_id).isdigit():
        raise ValueError("provider_id must be numeric")
    path = "/catalog/blueprints/" + str(int(blueprint_id)) + "/print_providers/" + str(int(provider_id)) + "/shipping.json"
    return request(path.replace("/catalog/", "/catalog/"))
