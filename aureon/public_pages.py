"""Credential-free public product-page research.

Fetches one operator-supplied HTTPS product URL, extracts only clearly published
product fields, and stores a timestamped observation. This is not a crawler,
price guarantee, or proof of sales/demand.
"""
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError
import hashlib
import ipaddress
import json
import socket

MAX_BYTES = 1_500_000
USER_AGENT = "AureonResearch/0.4 (+https://github.com/llakshyaa-rgb/Aureon)"


def _validate_public_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Enter one public HTTPS product URL.")
    parsed = urlsplit(url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS product URLs without embedded credentials are allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Local and private network URLs are not allowed.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError:
        raise ValueError("The product URL host could not be resolved.") from None
    if not addresses:
        raise ValueError("The product URL host has no public address.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError:
            raise ValueError("The product URL resolved to an invalid address.") from None
        if not ip.is_global:
            raise ValueError("Private, local, and reserved network addresses are blocked.")
    return url.strip()


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _ProductHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title_parts = []
        self.in_title = False
        self.jsonld = []
        self.in_jsonld = False
        self.jsonld_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = {str(k).lower(): v for k, v in attrs}
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
            value = attrs.get("content")
            if key and value:
                self.meta[key] = value.strip()
        if tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self.in_jsonld = True
            self.jsonld_parts = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_jsonld:
            raw = "".join(self.jsonld_parts).strip()
            if raw:
                try:
                    self.jsonld.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
            self.in_jsonld = False
            self.jsonld_parts = []

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_jsonld:
            self.jsonld_parts.append(data)


def _walk_products(value):
    if isinstance(value, list):
        for item in value:
            yield from _walk_products(item)
    elif isinstance(value, dict):
        kind = value.get("@type", [])
        kinds = [kind] if isinstance(kind, str) else kind if isinstance(kind, list) else []
        if any(str(x).lower() == "product" for x in kinds):
            yield value
        if "@graph" in value:
            yield from _walk_products(value["@graph"])


def _first_offer(product):
    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers if isinstance(offers, dict) else {}


def parse_product_page(html, url):
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Product page content is too large.")
    parser = _ProductHTML()
    parser.feed(html)
    product = next((p for block in parser.jsonld for p in _walk_products(block)), {})
    offer = _first_offer(product)
    title = (product.get("name") or parser.meta.get("og:title")
             or parser.meta.get("twitter:title") or " ".join(parser.title_parts)).strip()
    raw_price = (offer.get("price") or offer.get("lowPrice")
                 or parser.meta.get("product:price:amount")
                 or parser.meta.get("price"))
    price = None
    if raw_price is not None:
        try:
            candidate = float(str(raw_price).replace(",", "").strip())
            if candidate >= 0 and candidate < 1_000_000_000:
                price = round(candidate, 2)
        except (TypeError, ValueError):
            pass
    currency = (offer.get("priceCurrency") or parser.meta.get("product:price:currency")
                or parser.meta.get("pricecurrency") or "").upper()
    if len(currency) != 3 or not currency.isalpha():
        currency = None
    availability = offer.get("availability") or parser.meta.get("availability")
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    if not isinstance(brand, str):
        brand = parser.meta.get("brand")
    if not title:
        raise ValueError("No product title could be extracted from this page.")
    return {
        "title": title[:300], "price": price, "currency": currency,
        "availability": str(availability)[:120] if availability else None,
        "brand": brand[:120] if isinstance(brand, str) else None,
        "source_url": url, "price_found": price is not None,
        "evidence_type": "public_product_page_observation",
    }


def fetch_product_page(url, timeout=12):
    safe_url = _validate_public_url(url)
    request = Request(safe_url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })
    opener = build_opener(_SafeRedirect())
    try:
        with opener.open(request, timeout=max(3, min(int(timeout), 15)) as response:
            final_url = _validate_public_url(response.geturl())
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "html" not in content_type and "xhtml" not in content_type:
                raise RuntimeError("The URL did not return an HTML product page.")
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Could not retrieve product page: " + str(exc)[:300]) from exc
    if len(raw) > MAX_BYTES:
        raise RuntimeError("Product page exceeded the 1.5 MB research limit.")
    try:
        html = raw.decode("utf-8", "replace")
    except UnicodeError:
        raise RuntimeError("Product page text could not be decoded.") from None
    return parse_product_page(html, final_url)


def research_public_product_page(db_path, url):
    from .workflows import create_record
    observation = fetch_product_page(url)
    observed_at = datetime.now(timezone.utc).isoformat()
    observation["observed_at"] = observed_at
    observation["limitations"] = [
        "A displayed page price may exclude shipping, taxes, discounts or checkout changes.",
        "Availability and structured data are publisher-supplied and are not independently verified.",
        "One listing is not market-wide competitor coverage and does not establish demand or sales.",
    ]
    digest = hashlib.sha256((observation["source_url"] + observed_at[:10]).encode("utf-8")).hexdigest()
    record = create_record(db_path, "opportunity",
        "Public listing observation · " + observation["title"][:150],
        {"competitor_observation": observation,
         "evidence": [{"source_url": observation["source_url"],
                       "collected_at": observed_at,
                       "observation": "Public product-page fields extracted by Aureon"}],
         "research_status": "unverified_public_listing_observation"},
        "research", idempotency_key="public-product-" + digest)
    return {"observation": observation, "record": record,
            "warning": "Observed page data only; verify the price and shipping at checkout."}
