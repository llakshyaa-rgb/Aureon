"""Live public trend discovery using Google's public Trending RSS feed.

This is real external data, not operator-entered mock records. It is a discovery
signal only; it is not proof of product demand, sales, or supplier availability.
"""
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import re
import xml.etree.ElementTree as ET

BASE_URL = "https://trends.google.com/trending/rss"


def fetch_trending_searches(geo="IN", limit=25, timeout=12):
    if not isinstance(geo, str) or not re.fullmatch(r"[A-Za-z]{2}", geo):
        raise ValueError("geo must be a two-letter country code")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    url = BASE_URL + "?" + urlencode({"geo": geo.upper()})
    request = Request(url, headers={
        "User-Agent": "AureonCommerce/0.2 (+https://github.com/llakshyaa-rgb/Aureon)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    })
    try:
        with urlopen(request, timeout=max(3, min(int(timeout), 20))) as response:
            if response.status != 200:
                raise RuntimeError("Trends provider returned HTTP " + str(response.status))
            raw = response.read(2_000_000)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("Live trends are temporarily unavailable: " + str(exc)) from exc
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RuntimeError("Trends provider returned invalid RSS data") from exc
    items = []
    for node in root.findall(".//item")[:limit]:
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        items.append({
            "title": title,
            "traffic": (node.findtext("approx_traffic") or "").strip(),
            "published_at": (node.findtext("pubDate") or "").strip(),
            "link": (node.findtext("link") or "").strip(),
            "news": [
                {"title": (n.findtext("news_item_title") or "").strip(),
                 "url": (n.findtext("news_item_url") or "").strip(),
                 "source": (n.findtext("news_item_source") or "").strip()}
                for n in node.findall(".//news_item")[:3]
            ],
        })
    return {
        "provider": "Google Trends public Trending RSS",
        "geo": geo.upper(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
        "limitations": [
            "Trending searches are attention signals, not validated product demand or sales.",
            "Search trends do not establish supplier stock, pricing, shipping, or profitability.",
            "Use source links and independent validation before investing money.",
        ],
    }
