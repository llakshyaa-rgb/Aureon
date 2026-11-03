"""Explainable opportunity score from normalized analyst estimates."""
WEIGHTS = {"demand": 0.20, "trend": 0.15, "margin": 0.25,
           "competition": 0.20, "shipping": 0.10, "confidence": 0.10}

def score_opportunity(signals):
    missing = [name for name in WEIGHTS if name not in signals]
    if missing:
        raise ValueError("missing scoring signals: " + ", ".join(missing))
    values = {}
    for name in WEIGHTS:
        value = float(signals[name])
        if not 0 <= value <= 100:
            raise ValueError(name + " must be between 0 and 100")
        values[name] = value
    contributions = {name: round(values[name] * weight, 2) for name, weight in WEIGHTS.items()}
    total = round(sum(contributions.values()), 2)
    tier = "strong_candidate" if total >= 75 else "investigate" if total >= 55 else "weak_candidate"
    return {"score": total, "tier": tier, "contributions": contributions,
            "weights": WEIGHTS.copy(), "input_signals": values,
            "notes": ["Decision support, not a sales prediction.",
                      "Competition is reverse-scored: higher means lower saturation.",
                      "Confidence reflects source quality and recency."]}
