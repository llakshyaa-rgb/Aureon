"""Evidence-first product research helpers using explicitly supplied observations."""
import math
from datetime import datetime, timezone
from urllib.parse import urlparse
from .intelligence.scoring import score_opportunity


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
        if not isinstance(url, str):
            raise ValueError("each observation needs a public source URL")
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
        clean.append({"url": url, "title": str(item.get("title", ""))[:200],
                      "price": round(price, 2), "currency": str(item.get("currency", "USD")).upper(),
                      "reviews": reviews, "availability": str(item.get("availability", "unknown"))[:80],
                      "collected_at": dt.astimezone(timezone.utc).isoformat()})
    if not clean:
        raise ValueError("at least one unique valid observation is required")
    currencies = {x["currency"] for x in clean}
    if len(currencies) != 1 or any(len(x) != 3 or not x.isalpha() for x in currencies):
        raise ValueError("all observed prices must use one valid currency")
    return clean


def analyze_competition(observations):
    items = validate_observations(observations)
    prices = sorted(x["price"] for x in items)
    reviews = [x["reviews"] for x in items]
    n = len(items)
    median = prices[n // 2] if n % 2 else (prices[n//2-1] + prices[n//2]) / 2
    availability = sum(x["availability"].lower() in {"in stock", "available"} for x in items)
    concentration = max(reviews) / max(1, sum(reviews))
    # This is a transparent heuristic over supplied observations, not a market census.
    saturation = min(100, round(20 + min(n, 30) * 1.6 + min(sum(reviews), 10000) / 250
                                  + concentration * 15, 1))
    return {"observation_count": n, "currency": items[0]["currency"],
            "price_min": round(prices[0], 2), "price_median": round(median, 2),
            "price_max": round(prices[-1], 2), "review_total": sum(reviews),
            "availability_observed": availability, "saturation_heuristic": saturation,
            "observations": items,
            "limitations": ["Only supplied URLs and observations are included.",
                            "No marketplace crawl, sales volume, market share or demand is inferred.",
                            "Saturation is a heuristic, not a verified market-wide measure."]}
