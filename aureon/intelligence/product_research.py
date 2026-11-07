"""Evidence-first competitor analysis from explicitly supplied observations."""
import math
from datetime import datetime, timezone
from urllib.parse import urlparse
from collections import Counter


def _number(value, label, minimum=0, maximum=100000000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(label + " must be between " + str(minimum) + " and " + str(maximum))
    return float(value)


def validate_observations(observations):
    if not isinstance(observations, list) or not 1 <= len(observations) <= 100:
        raise ValueError("observations must contain 1-100 entries")
    clean, seen = [], set()
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError("each observation must be an object")
        url = item.get("url")
        if not isinstance(url, str) or not url.strip() or len(url) > 2048 or url != url.strip() or any(ord(ch) < 33 for ch in url):
            raise ValueError("each observation needs a valid public source URL")
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("observation URLs must be public HTTP(S) URLs")
        if url in seen:
            continue
        seen.add(url)
        price = _number(item.get("price"), "price")
        reviews = item.get("reviews", 0)
        if isinstance(reviews, bool) or not isinstance(reviews, int) or not 0 <= reviews <= 100000000:
            raise ValueError("reviews must be a non-negative integer")
        collected = item.get("collected_at")
        if not isinstance(collected, str):
            raise ValueError("collected_at must be timezone-aware ISO-8601")
        try:
            dt = datetime.fromisoformat(collected.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError()
        except ValueError:
            raise ValueError("collected_at must be timezone-aware ISO-8601") from None
        currency = str(item.get("currency", "USD")).upper()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        clean.append({
            "url": url, "domain": (parsed.hostname or "").lower(),
            "title": str(item.get("title", ""))[:200],
            "price": round(price, 2), "currency": currency,
            "reviews": reviews, "availability": str(item.get("availability", "unknown"))[:80],
            "collected_at": dt.astimezone(timezone.utc).isoformat(),
        })
    if not clean:
        raise ValueError("at least one unique valid observation is required")
    currencies = {x["currency"] for x in clean}
    if len(currencies) != 1:
        raise ValueError("all observed prices must use one currency")
    return clean


def _percentile(values, fraction):
    if not values:
        return 0.0
    position = (len(values) - 1) * fraction
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return values[low]
    return values[low] + (values[high] - values[low]) * (position - low)


def analyze_competition(observations):
    items = validate_observations(observations)
    prices = sorted(x["price"] for x in items)
    reviews = [x["reviews"] for x in items]
    now = datetime.now(timezone.utc)
    ages = []
    for item in items:
        collected = datetime.fromisoformat(item["collected_at"])
        ages.append(max(0.0, (now - collected).total_seconds() / 86400))
    n = len(items)
    median = _percentile(prices, .5)
    q1, q3 = _percentile(prices, .25), _percentile(prices, .75)
    availability = sum(x["availability"].lower() in {"in stock", "available"} for x in items)
    total_reviews = sum(reviews)
    concentration = max(reviews) / max(1, total_reviews)
    saturation = min(100, round(20 + min(n, 30) * 1.6 + min(total_reviews, 10000) / 250
                                  + concentration * 15, 1))
    age_sorted = sorted(ages)
    freshness = "fresh" if max(ages) <= 7 else "mixed" if median <= 30 else "stale"
    sample_confidence = "low" if n < 5 else "moderate" if n < 15 else "sampled"
    domain_counts = Counter(x["domain"] for x in items)
    return {
        "observation_count": n, "currency": items[0]["currency"],
        "price_min": round(prices[0], 2), "price_q1": round(q1, 2),
        "price_median": round(median, 2), "price_q3": round(q3, 2),
        "price_max": round(prices[-1], 2), "price_spread": round(prices[-1] - prices[0], 2),
        "review_total": total_reviews, "review_median": round(_percentile(sorted(reviews), .5), 1),
        "availability_observed": availability,
        "availability_rate_percent": round(availability / n * 100, 1),
        "saturation_heuristic": saturation,
        "sample_confidence": sample_confidence,
        "freshness": freshness, "oldest_observation_days": round(max(ages), 1),
        "newest_observation_days": round(min(ages), 1),
        "source_domain_count": len(domain_counts),
        "source_domains": dict(domain_counts),
        "observations": items,
        "limitations": [
            "Only supplied URLs and observations are included; Aureon does not crawl marketplaces here.",
            "Review counts and availability are snapshots, not sales volume or verified stock.",
            "Saturation is a heuristic, not a verified market-wide measure.",
            "A small or concentrated sample has low confidence; do not generalise beyond these sources.",
        ],
    }
