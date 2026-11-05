"""Persistent A/B campaign experiments with transparent, non-statistical comparisons."""
import json
from .db import connect, json_dump
from .workflows import create_record


def create_experiment(db_path, name, hypothesis, channel, variants):
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise ValueError("experiment name is required")
    if not isinstance(hypothesis, str) or not hypothesis.strip() or len(hypothesis) > 1000:
        raise ValueError("hypothesis is required")
    if channel not in {"instagram", "tiktok", "pinterest", "email", "facebook"}:
        raise ValueError("unsupported experiment channel")
    if not isinstance(variants, list) or not 2 <= len(variants) <= 5:
        raise ValueError("experiments need 2-5 variants")
    clean, seen = [], set()
    for item in variants:
        if not isinstance(item, dict):
            raise ValueError("each variant must be an object")
        key, label = item.get("key"), item.get("label")
        if not isinstance(key, str) or not key.strip() or len(key) > 40 or key in seen:
            raise ValueError("variant keys must be unique non-empty text")
        if not isinstance(label, str) or not label.strip() or len(label) > 120:
            raise ValueError("variant labels are required")
        seen.add(key)
        clean.append({"key": key, "label": label.strip(), "description": str(item.get("description", ""))[:500],
                      "observations": []})
    return create_record(db_path, "campaign", name.strip(), {
        "experiment": True, "hypothesis": hypothesis.strip(), "channel": channel,
        "variants": clean, "publication_status": "draft_only",
        "spend_status": "not_authorized", "metric_observations": []
    }, "draft")


def record_variant_observation(db_path, experiment_id, variant_key, metrics):
    from .analytics import campaign_metrics
    if not isinstance(variant_key, str) or not variant_key:
        raise ValueError("variant_key is required")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")
    currency = metrics.get("currency", "USD")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ValueError("currency must be a three-letter code")
    computed = campaign_metrics(metrics)
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='campaign'", (experiment_id,)).fetchone()
        if row is None:
            raise ValueError("experiment not found")
        data = json.loads(row["data_json"])
        if not data.get("experiment"):
            raise ValueError("campaign is not an A/B experiment")
        variants = data.get("variants", [])
        variant = next((x for x in variants if x["key"] == variant_key), None)
        if variant is None:
            raise ValueError("variant not found")
        currency = currency.upper()
        if variant["observations"] and variant["observations"][-1]["currency"] != currency:
            raise ValueError("all observations for a variant must use one currency")
        if any(x["observations"] and x["observations"][-1]["currency"] != currency
               for x in variants if x["key"] != variant_key):
            raise ValueError("all experiment variants must use the same currency")
        observation = {**computed, "currency": currency}
        variant["observations"].append(observation)
        conn.execute("UPDATE workspace_records SET data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                     (json_dump(data), experiment_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
                     ("marketing.experiment.observed", "campaign", str(experiment_id),
                      json_dump({"variant": variant_key, "impressions": computed["impressions"],
                                 "observed_currency": currency})))
    return observation


def compare_experiment(db_path, experiment_id):
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='campaign'", (experiment_id,)).fetchone()
    if row is None:
        raise ValueError("experiment not found")
    data = json.loads(row["data_json"])
    if not data.get("experiment"):
        raise ValueError("campaign is not an A/B experiment")
    result = []
    for variant in data.get("variants", []):
        observations = variant.get("observations", [])
        if not observations:
            result.append({"key": variant["key"], "label": variant["label"], "impressions": 0,
                           "clicks": 0, "orders": 0, "conversion_rate": None,
                           "return_on_ad_spend": None, "currency": None})
            continue
        currencies = {x["currency"] for x in observations}
        if len(currencies) != 1:
            raise ValueError("variant has mixed currencies")
        totals = {key: sum(x[key] for x in observations)
                  for key in ("impressions", "clicks", "orders", "spend", "revenue")}
        result.append({"key": variant["key"], "label": variant["label"],
                       **totals, "currency": next(iter(currencies)),
                       "click_through_rate": round(totals["clicks"] / totals["impressions"], 4) if totals["impressions"] else None,
                       "conversion_rate": round(totals["orders"] / totals["clicks"], 4) if totals["clicks"] else None,
                       "return_on_ad_spend": round(totals["revenue"] / totals["spend"], 4) if totals["spend"] else None})
    measured = [x for x in result if x["impressions"] > 0 and x["conversion_rate"] is not None]
    winner = max(measured, key=lambda x: (x["conversion_rate"], x["return_on_ad_spend"] or 0)) if measured else None
    return {"experiment_id": experiment_id, "hypothesis": data.get("hypothesis"),
            "variants": result, "leading_variant": winner,
            "warning": "Descriptive comparison only. No statistical significance, causal lift or platform attribution is inferred. Ensure variants received comparable audiences and time windows."}
