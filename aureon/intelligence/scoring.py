"""Explainable opportunity score from normalized analyst estimates."""
import math
WEIGHTS={"demand":0.20,"trend":0.15,"margin":0.25,"competition":0.20,"shipping":0.10,"confidence":0.10}
def score_opportunity(signals):
 if not isinstance(signals,dict):raise ValueError("signals must be an object")
 missing=[n for n in WEIGHTS if n not in signals]
 if missing:raise ValueError("missing scoring signals: "+", ".join(missing))
 values={}
 for name in WEIGHTS:
  raw=signals[name]
  if isinstance(raw,bool):raise ValueError(name+" must be a number from 0 to 100")
  try:value=float(raw)
  except (TypeError,ValueError) as exc:raise ValueError(name+" must be a number from 0 to 100") from exc
  if not math.isfinite(value) or not 0<=value<=100:raise ValueError(name+" must be finite and between 0 and 100")
  values[name]=value
 contributions={name:round(values[name]*weight,2) for name,weight in WEIGHTS.items()}
 total=round(sum(contributions.values()),2)
 tier="strong_candidate" if total>=75 else "investigate" if total>=55 else "weak_candidate"
 return {"score":total,"tier":tier,"contributions":contributions,"weights":WEIGHTS.copy(),
 "input_signals":values,"notes":["Decision support, not a sales prediction.","Competition is reverse-scored: higher means lower saturation.","Confidence reflects source quality and recency."]}
