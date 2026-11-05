"""Live public trend discovery using Google's public Trending RSS feed.

This is real external data, not operator-entered mock records. It is a discovery
signal only; it is not proof of product demand, sales, or supplier availability.
"""
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import re
import json
import xml.etree.ElementTree as ET
from .db import connect,json_dump

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



def collect_trends(db_path, geo="IN", limit=25):
    """Persist deduplicated live search signals as research-stage opportunities."""
    from urllib.parse import urlparse
    from .workflows import create_record, list_records

    result = fetch_trending_searches(geo, limit)
    with connect(db_path) as conn:
        snapshot = {"geo": result["geo"], "fetched_at": result["fetched_at"],
                    "items": [{"title": item["title"], "traffic": item["traffic"],
                               "published_at": item["published_at"], "link": item["link"]}
                              for item in result["items"]]}
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
                     ("trends.snapshot", "trend_snapshot", result["geo"], json_dump(snapshot)))
    existing = list_records(db_path, "opportunity", 250)
    known = {
        (row["data"].get("trend_geo"), row["data"].get("trend_title"),
         row["data"].get("trend_published_at"))
        for row in existing
    }
    created = []
    for item in result["items"]:
        key = (result["geo"], item["title"], item["published_at"])
        if key in known:
            continue
        source_url = item["link"] or (BASE_URL + "?geo=" + result["geo"])
        if urlparse(source_url).scheme not in {"http", "https"}:
            source_url = BASE_URL + "?geo=" + result["geo"]
        record = create_record(
            db_path, "opportunity", item["title"],
            {"evidence": [{"source_url": source_url,
                           "collected_at": result["fetched_at"],
                           "published_at": item["published_at"]}],
             "trend_provider": result["provider"], "trend_geo": result["geo"],
             "trend_title": item["title"], "trend_published_at": item["published_at"],
             "trend_traffic": item["traffic"], "related_news": item["news"],
             "research_status": "unvalidated_trend_signal"},
            "research")
        )
        created.append(record["id"])
        known.add(key)
    return {"provider": result["provider"], "geo": result["geo"],
            "fetched_at": result["fetched_at"], "fetched": result["count"],
            "created": len(created), "record_ids": created,
            "note": "Trend signals are not verified demand or sales."}


def trend_history(db_path, geo="IN", limit=100):
    """Return saved RSS snapshots and rank movement; only collected snapshots are compared."""
    if not isinstance(geo, str) or not re.fullmatch(r"[A-Za-z]{2}", geo):
        raise ValueError("geo must be a two-letter country code")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT data_json FROM events WHERE topic='trends.snapshot' AND entity_id=? ORDER BY id DESC LIMIT ?",
            (geo.upper(), limit)).fetchall()
    snapshots = [json.loads(row["data_json"]) for row in reversed(rows)]
    movement = {}
    if len(snapshots) >= 2:
        previous = {item["title"]: rank for rank, item in enumerate(snapshots[-2]["items"], 1)}
        latest = {item["title"]: rank for rank, item in enumerate(snapshots[-1]["items"], 1)}
        for title in sorted(set(previous) & set(latest)):
            movement[title] = {"previous_rank": previous[title], "latest_rank": latest[title],
                               "movement": previous[title] - latest[title],
                               "direction": "rising" if latest[title] < previous[title] else "falling" if latest[title] > previous[title] else "steady"}
    return {"geo": geo.upper(), "snapshots": snapshots, "snapshot_count": len(snapshots),
            "rank_movement": movement,
            "warning": "Rank movement compares only Aureon-collected RSS snapshots. Missing snapshots are not inferred; this is not search volume or product demand."}
