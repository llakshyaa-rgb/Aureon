"""Shopify Admin API provider health and read-only store inspection."""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_VERSION = "2026-10"


def configured():
    store = os.getenv("AUREON_SHOPIFY_STORE", "").strip().lower()
    token = os.getenv("AUREON_SHOPIFY_ACCESS_TOKEN", "").strip()
    if store and not store.endswith(".myshopify.com"):
        store += ".myshopify.com"
    return store, token


def health():
    store, token = configured()
    return {"name": "Shopify", "configured": bool(store and token),
            "store": store or None, "mode": "live" if store and token else "disconnected"}


def graphql(query, variables=None):
    store, token = configured()
    if not store or not token:
        raise RuntimeError("Shopify credentials are not configured.")
    url = "https://" + store + "/admin/api/" + API_VERSION + "/graphql.json"
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = Request(url, data=body, headers={
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    })
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(2_000_000))
    except HTTPError as exc:
        raise RuntimeError("Shopify HTTP " + str(exc.code) + "; check credentials and API scopes.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not reach Shopify; check network and store domain.") from None
    if payload.get("errors"):
        raise RuntimeError("Shopify GraphQL request failed: " + "; ".join(
            str(x.get("message", "error")) for x in payload["errors"][:3]))
    return payload.get("data") or {}


def shop_info():
    result = graphql("query { shop { name myshopifyDomain currencyCode } }")
    return result.get("shop") or {}


def products(limit=25):
    if not 1 <= int(limit) <= 100:
        raise ValueError("limit must be between 1 and 100")
    result = graphql(
        "query Products($n: Int!) { products(first: $n, sortKey: UPDATED_AT, reverse: true) "
        "{ nodes { id title handle status vendor productType updatedAt } } }",
        {"n": int(limit)})
    return (result.get("products") or {}).get("nodes", [])
