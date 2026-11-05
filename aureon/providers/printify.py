"""Printify shop/catalog discovery, artwork upload and hidden product creation."""
import json
import os
import math
import ipaddress
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
    url = str(image_url or "").strip()
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if (not file_name or len(file_name) > 180 or "/" in file_name or chr(92) in file_name
            or any(ord(char) < 32 for char in file_name)):
        raise ValueError("file_name must be a simple filename")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("image_url must be a public HTTPS URL without embedded credentials")
    if any(char.isspace() for char in parsed.netloc) or host == "localhost" or host.endswith((".localhost", ".local")):
        raise ValueError("image_url must use a public hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("image_url must use a public hostname, not an IP address")
    result = request("/uploads/images.json", method="POST",
                     body={"file_name": file_name, "url": url})
    if not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError("Printify did not confirm image upload.")
    return result


def validate_product(shop_id, product):
    if isinstance(shop_id, bool) or not str(shop_id).isdigit() or int(shop_id) < 1:
        raise ValueError("shop_id must be a positive integer")
    if not isinstance(product, dict):
        raise ValueError("product must be an object")
    title = product.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 255:
        raise ValueError("product title is required and must be 255 characters or fewer")
    clean = dict(product)
    clean["title"] = title.strip()
    for key in ("blueprint_id", "print_provider_id"):
        value = product.get(key)
        if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
            raise ValueError(key + " must be a positive integer")
        clean[key] = int(value)
    description = product.get("description", "")
    if not isinstance(description, str) or len(description) > 5000:
        raise ValueError("description must be text of at most 5000 characters")
    if "tags" in product and (not isinstance(product["tags"], list) or
                              any(not isinstance(tag, str) for tag in product["tags"])):
        raise ValueError("tags must be a list of text values")
    if "safety_information" in product and not isinstance(product["safety_information"], str):
        raise ValueError("safety_information must be text")
    if "print_details" in product and not isinstance(product["print_details"], dict):
        raise ValueError("print_details must be an object")
    variants_data = product.get("variants")
    if not isinstance(variants_data, list) or not variants_data:
        raise ValueError("at least one variant is required")
    variant_ids = []
    normalized_variants = []
    for variant in variants_data:
        if not isinstance(variant, dict):
            raise ValueError("each variant must be an object")
        variant_id = variant.get("id")
        price = variant.get("price")
        if isinstance(variant_id, bool) or not str(variant_id).isdigit() or int(variant_id) < 1:
            raise ValueError("each variant requires a positive numeric id")
        if int(variant_id) in variant_ids:
            raise ValueError("variant IDs must be unique")
        if isinstance(price, bool) or not isinstance(price, int) or price < 1:
            raise ValueError("each variant requires a positive integer price in provider minor units")
        if not isinstance(variant.get("is_enabled"), bool):
            raise ValueError("each variant requires is_enabled")
        variant_ids.append(int(variant_id))
        normalized_variants.append({"id": int(variant_id), "price": price, "is_enabled": variant["is_enabled"]})
    areas = product.get("print_areas")
    if not isinstance(areas, list) or not areas:
        raise ValueError("at least one print area is required")
    normalized_areas = []
    for area in areas:
        if not isinstance(area, dict):
            raise ValueError("each print area must be an object")
        area_variants = area.get("variant_ids")
        placeholders = area.get("placeholders")
        if not isinstance(area_variants, list) or not area_variants or not isinstance(placeholders, list) or not placeholders:
            raise ValueError("each print area requires variant_ids and placeholders")
        normalized_area_ids = []
        for variant_id in area_variants:
            if isinstance(variant_id, bool) or not str(variant_id).isdigit() or int(variant_id) not in variant_ids:
                raise ValueError("print area variant_ids must reference variants in this product")
            normalized_area_ids.append(int(variant_id))
        if len(set(normalized_area_ids)) != len(normalized_area_ids):
            raise ValueError("print area variant_ids must be unique")
        normalized_placeholders = []
        for placeholder in placeholders:
            if not isinstance(placeholder, dict):
                raise ValueError("each print placeholder must be an object")
            if not isinstance(placeholder.get("position"), str) or not placeholder["position"].strip():
                raise ValueError("each print placeholder requires a position")
            if not isinstance(placeholder.get("decoration_method"), str) or not placeholder["decoration_method"].strip():
                raise ValueError("each print placeholder requires a decoration_method")
            images = placeholder.get("images")
            if not isinstance(images, list) or not images:
                raise ValueError("each print placeholder requires at least one uploaded image")
            for image in images:
                if not isinstance(image, dict) or not isinstance(image.get("id"), str) or not image["id"].strip():
                    raise ValueError("print images must reference uploaded Printify media IDs")
                for coordinate in ("x", "y", "scale", "angle"):
                    value = image.get(coordinate)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                        raise ValueError("image " + coordinate + " must be a finite number")
            normalized_placeholders.append(placeholder)
        normalized_areas.append({**area, "variant_ids": normalized_area_ids, "placeholders": normalized_placeholders})
    clean["variants"] = normalized_variants
    clean["print_areas"] = normalized_areas
    allowed = {"title", "description", "blueprint_id", "print_provider_id",
               "variants", "print_areas", "tags", "safety_information", "print_details"}
    clean = {key: value for key, value in clean.items() if key in allowed}
    # Printify products default to visible in the connected sales channel.
    # Aureon intentionally creates hidden products only; publishing is a separate future feature.
    clean["visible"] = False
    return int(shop_id), clean


def create_product(shop_id, product):
    shop_id, payload = validate_product(shop_id, product)
    result = request("/shops/" + str(shop_id) + "/products.json",
                     method="POST", body=payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError("Printify did not confirm product creation.")
    if result.get("visible") is True:
        raise RuntimeError("Printify created product " + str(result.get("id")) + " but returned visible=true despite Aureon's hidden-product request; verify it in Printify immediately.")
    return result
