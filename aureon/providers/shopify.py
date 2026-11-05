"""Shopify Admin GraphQL provider: read catalog and create unpublished drafts."""
import html
import json
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_VERSION = "2026-10"


def configured():
    store = os.getenv("AUREON_SHOPIFY_STORE", "").strip().lower()
    token = os.getenv("AUREON_SHOPIFY_ACCESS_TOKEN", "").strip()
    if store and not store.endswith(".myshopify.com"):
        store += ".myshopify.com"
    if store and not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", store):
        raise ValueError("AUREON_SHOPIFY_STORE must be a myshopify.com domain")
    return store, token


def health():
    store, token = configured()
    ready = bool(store and token)
    return {"name": "Shopify Admin GraphQL", "configured": ready,
            "connected": False, "store": store or None,
            "mode": "credentials_configured" if ready else "disconnected",
            "detail": "Connection check not yet run." if ready else
            "Set AUREON_SHOPIFY_STORE and AUREON_SHOPIFY_ACCESS_TOKEN."}


def graphql(query, variables=None):
    store, token = configured()
    if not store or not token:
        raise RuntimeError("Shopify credentials are not configured.")
    url = "https://" + store + "/admin/api/" + API_VERSION + "/graphql.json"
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Shopify-Access-Token": token,
        "User-Agent": "AureonCommerce/0.3",
    })
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(2_000_000))
    except HTTPError as exc:
        raise RuntimeError("Shopify HTTP " + str(exc.code) +
                           "; check store, token and API scopes.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not reach Shopify; check network and store domain.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Shopify returned an invalid response.") from None
    if payload.get("errors"):
        messages = [str(x.get("message", "GraphQL error")) for x in payload["errors"][:4]]
        raise RuntimeError("Shopify GraphQL: " + "; ".join(messages))
    return payload.get("data") or {}


def shop_info():
    result = graphql("query AureonShop { shop { name myshopifyDomain currencyCode } }")
    shop = result.get("shop")
    if not shop:
        raise RuntimeError("Shopify did not return shop details.")
    return shop


def products(limit=25):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    result = graphql(
        "query AureonProducts($n: Int!) { products(first: $n, sortKey: UPDATED_AT, reverse: true) "
        "{ nodes { id title handle status vendor productType updatedAt } } }",
        {"n": limit})
    return (result.get("products") or {}).get("nodes", [])


def create_draft_product(title, description="", vendor="", product_type="", tags=None):
    title = str(title or "").strip()
    description = str(description or "")
    if not title or len(title) > 255:
        raise ValueError("title is required and must be 255 characters or fewer")
    if len(description) > 5000:
        raise ValueError("description must be 5000 characters or fewer")
    if not isinstance(tags, (list, tuple)):
        tags = []
    clean_tags = [str(tag).strip()[:80] for tag in tags if str(tag).strip()][:20]
    product = {
        "title": title,
        "descriptionHtml": "<p>" + html.escape(description) + "</p>" if description else "",
        "vendor": str(vendor or "")[:255],
        "productType": str(product_type or "")[:255],
        "tags": clean_tags,
        "status": "DRAFT",
    }
    result = graphql(
        "mutation AureonCreateDraft($product: ProductCreateInput!) { "
        "productCreate(product: $product) { product { id title handle status } "
        "userErrors { field message } } }",
        {"product": product})
    response = result.get("productCreate") or {}
    errors = response.get("userErrors") or []
    if errors:
        raise RuntimeError("Shopify rejected draft: " + "; ".join(
            str(x.get("message", "invalid product")) for x in errors[:5]))
    created = response.get("product")
    if not created:
        raise RuntimeError("Shopify did not confirm draft creation.")
    return created
