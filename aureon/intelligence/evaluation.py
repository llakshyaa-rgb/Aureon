"""Integrated opportunity evaluation from evidence, competition and unit economics."""
from .scoring import score_opportunity
from .economics import Offer, calculate_unit_economics
from .product_research import analyze_competition
from ..research import validate_evidence
from ..workflows import create_record


def evaluate_product_opportunity(db_path, title, evidence, signals, observations, offer,
                                 region="global", business_model="undecided"):
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("title must be 1-200 characters")
    if not isinstance(region, str) or not region.strip():
        raise ValueError("region is required")
    if not isinstance(business_model, str) or not business_model.strip():
        raise ValueError("business_model is required")
    if not isinstance(signals, dict):
        raise ValueError("signals must be an object")
    required = {"demand", "trend", "shipping", "confidence"}
    missing = required - set(signals)
    if missing:
        raise ValueError("missing analyst signals: " + ", ".join(sorted(missing)))
    evidence = validate_evidence(evidence)
    competition = analyze_competition(observations)
    if not isinstance(offer, dict):
        raise ValueError("offer must be an object")
    offer = Offer(**offer)
    economics = calculate_unit_economics(offer)
    if economics["currency"] != competition["currency"]:
        raise ValueError("offer and competitor observations must use the same currency")
    margin_score = max(0, min(100, economics["profit_margin"] * 200))
    score_inputs = {**signals, "competition": 100 - competition["saturation_heuristic"],
                    "margin": margin_score}
    score = score_opportunity(score_inputs)
    decision = "shortlist_for_human_review" if score["tier"] == "strong_candidate" and economics["estimated_profit"] > 0 else "investigate"
    payload = {"evidence": evidence, "analyst_signals": signals,
               "competition": competition, "unit_economics": economics,
               "score": score, "region": region.strip()[:80],
               "business_model": business_model.strip()[:50],
               "decision": decision,
               "limitations": ["Demand, trend, shipping and confidence inputs are analyst-supplied.",
                               "Competitor observations are manually supplied and not a market-wide crawl.",
                               "Economics are estimates; taxes, duties and fees require local verification."]}
    record = create_record(db_path, "opportunity", title.strip(), payload,
                           "shortlisted" if decision == "shortlist_for_human_review" else "investigate")
    return {"record": record, "score": score, "economics": economics,
            "competition": competition, "decision": decision}
