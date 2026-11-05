"""Printify read-only shop and catalog discovery."""
import json
import os
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://api.printify.com/v1"
BASE_V2 = "https://api.printify.com/v2"


def health():
    token = os.getenv("AUREON_PRINTIFY_API_TOKEN", "").strip()
    return {"name": "Printify", "configured": bool(token),
            "mode": "credentials_configured" if token else "disconnected"}


def request(path, version=1, method="GET", body=None):
    token = os.getenv("AUREON_PRINTIFY_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Printify token is not configured.")
    if not path.startswith("/") or ".." in path or "#" in path:
        raise ValueError("invalid Printify API path")
    base = BASE_V2 if version == 2 else BASE
    if method not in {"GET", "POST"}:
        raise ValueError("unsupported Printify request method")
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(base + path, data=encoded, method=method, headers={
        "Authorization": "Bearer " + token,
        "User-Agent": "AureonCommerce/0.3",
        "Accept": "application/json",
        "Content-Type": "application/json",
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
    return request(path, version=2)


def upload_image_url(file_name, image_url):
    file_name = str(file_name or "").strip()
    parsed = urlparse(str(image_url or "").strip())
    if not file_name or len(file_name) > 180 or "/" in file_name or "\\\\" in file_name:
        raise ValueError("file_name must be a simple filename")
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("image_url must be a public HTTPS URL")
    result = request("/uploads/images.json", method="POST",
                     body={"file_name": file_name, "url": image_url})
    if not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError("Printify did not confirm image upload.")
    return result


def create_product(shop_id, product):
    if isinstance(shop_id, bool) or not str(shop_id).isdigit():
        raise ValueError("shop_id must be numeric")
    if not isinstance(product, dict):
        raise ValueError("product must be an object")
    title = product.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 255:
        raise ValueError("product title is required and must be 255 characters or fewer")
    for key in ("blueprint_id", "print_provider_id"):
        if isinstance(product.get(key), bool) or not str(product.get(key, "")).isdigit():
            raise ValueError(key + " must be numeric")
    variants_data = product.get("variants")
    if not isinstance(variants_data, list) or not variants_data:
        raise ValueError("at least one variant is required")
    for variant in variants_data:
        if not isinstance(variant, dict) or not str(variant.get("id", "")).isdigit():
            raise ValueError("each variant requires a numeric id")
        if isinstance(variant.get("price"), bool) or not isinstance(variant.get("price"), int) or variant["price"] < 1:
            raise ValueError("each variant requires a positive integer price in the provider currency's minor units")
        if not isinstance(variant.get("is_enabled"), bool):
            raise ValueError("each variant requires is_enabled")
    areas = product.get("print_areas")
    if not isinstance(areas, list) or not areas:
        raise ValueError("at least one print area is required")
    for area in areas:
        if not isinstance(area, dict) or not isinstance(area.get("variant_ids"), list) or not isinstance(area.get("placeholders"), list):
            raise ValueError("each print area requires variant_ids and placeholders")
        for placeholder in area["placeholders"]:
            images = placeholder.get("images") if isinstance(placeholder, dict) else None
            if not isinstance(images, list) or not images:
                raise ValueError("each print placeholder requires at least one uploaded image")
            for image in images:
                if not isinstance(image, dict) or not image.get("id"):
                    raise ValueError("print images must reference uploaded Printify media IDs")
    allowed = {"title", "description", "blueprint_id", "print_provider_id",
               "variants", "print_areas", "tags", "safety_information"}
    payload = {key: value for key, value in product.items() if key in allowed}
    result = request("/shops/" + str(int(shop_id)) + "/products.json",
                     method="POST", body=payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError("Printify did not confirm product creation.")
    return result
