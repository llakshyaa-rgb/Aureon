"""Supplier profiles and comparable, freshness-labelled manual quotes."""
import math,re,json
from datetime import datetime,timezone
from urllib.parse import urlparse
from .workflows import create_record,list_records
from .db import connect,json_dump
def add_supplier(db_path,name,provider,product_type,website=None,notes=""):
 for label,value,limit in (("name",name,200),("provider",provider,80),("product_type",product_type,100)):
  if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError(label+" is required and must be <= "+str(limit)+" characters")
 if website is not None:
  if not isinstance(website,str):raise ValueError("website must be a URL")
  u=urlparse(website)
  if u.scheme not in {"http","https"} or not u.netloc or u.username or u.password:raise ValueError("website must be a public http(s) URL")
 if not isinstance(notes,str):raise ValueError("notes must be text")
 return create_record(db_path,"supplier",name.strip(),{"provider":provider.strip(),"product_type":product_type.strip(),"website":website,"notes":notes[:500],"quotes":[],"verification":"unverified"},"research")
def add_quote(db_path,supplier_id,quote):
 if not isinstance(quote,dict):raise ValueError("quote must be an object")
 if any(k not in quote for k in ("product_cost","shipping_cost","currency","destination","quoted_at")):raise ValueError("quote missing required fields")
 costs={}
 for key in ("product_cost","shipping_cost"):
  v=quote[key]
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError(key+" must be finite and non-negative")
  costs[key]=round(float(v),2)
 currency=quote["currency"];destination=quote["destination"];stamp=quote["quoted_at"]
 if not isinstance(currency,str) or not re.fullmatch(r"[A-Za-z]{3}",currency):raise ValueError("currency must be a three-letter code")
 if not isinstance(destination,str) or not destination.strip() or len(destination)>100:raise ValueError("destination is required")
 if not isinstance(stamp,str):raise ValueError("quoted_at must be timezone-aware ISO-8601")
 try:
  dt=datetime.fromisoformat(stamp.replace("Z","+00:00"))
  if dt.tzinfo is None:raise ValueError()
 except Exception as exc:raise ValueError("quoted_at must be timezone-aware ISO-8601") from exc
 if dt.astimezone(timezone.utc).timestamp() > datetime.now(timezone.utc).timestamp() + 300:
  raise ValueError("quoted_at cannot be more than five minutes in the future")
 with connect(db_path) as conn:
  conn.execute("BEGIN IMMEDIATE");row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='supplier'",(supplier_id,)).fetchone()
  if row is None:raise ValueError("supplier not found")
  data=json.loads(row["data_json"]);item={"product_cost":costs["product_cost"],"shipping_cost":costs["shipping_cost"],"currency":currency.upper(),"destination":destination.strip(),"quoted_at":stamp,"status":"unverified","reference":str(quote.get("reference",""))[:150],"notes":str(quote.get("notes",""))[:500]}
  data.setdefault("quotes",[]).append(item)
  conn.execute("UPDATE workspace_records SET data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(json_dump(data),supplier_id))
  conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",("supplier.quote.added","supplier",str(supplier_id),json_dump({"destination":item["destination"],"currency":item["currency"],"quote_index":len(data["quotes"])-1})))
 return item
def compare_supplier_quotes(db_path,product_type,destination,currency):
 if not all(isinstance(x,str) and x.strip() for x in (product_type,destination,currency)):raise ValueError("product_type, destination and currency are required")
 if not re.fullmatch(r"[A-Za-z]{3}",currency):raise ValueError("currency must be a three-letter code")
 now=datetime.now(timezone.utc);candidates=[]
 for supplier in list_records(db_path,"supplier",250):
  if supplier["data"].get("product_type","").casefold()!=product_type.strip().casefold():continue
  for q in supplier["data"].get("quotes",[]):
   if q["destination"].casefold()!=destination.strip().casefold() or q["currency"]!=currency.upper():continue
   quoted=datetime.fromisoformat(q["quoted_at"].replace("Z","+00:00")).astimezone(timezone.utc)
   age_days=max(0,(now-quoted).total_seconds()/86400)
   freshness="fresh" if age_days<=7 else "aging" if age_days<=30 else "stale"
   candidates.append({"supplier_id":supplier["id"],"supplier":supplier["title"],"provider":supplier["data"].get("provider"),
    "landed_cost":round(q["product_cost"]+q["shipping_cost"],2),"currency":currency.upper(),"quoted_at":q["quoted_at"],
    "age_days":round(age_days,1),"freshness":freshness,"status":q.get("status","unverified"),"quote":q})
 candidates.sort(key=lambda x:(x["landed_cost"],x["age_days"]))
 return {"quotes":candidates,"best_quote":candidates[0] if candidates else None,
 "warning":"Quotes are user-supplied and unverified. Freshness is based on quote timestamp, not supplier confirmation. Confirm stock, quality, shipping, duties, taxes and current price."}


def prepare_order_from_best_quote(db_path, product_title, quantity, product_type, destination, currency):
    """Prepare a simulated purchase order from the lowest comparable manual quote."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 10000:
        raise ValueError("quantity must be 1..10000")
    comparison = compare_supplier_quotes(db_path, product_type, destination, currency)
    fresh_quotes = [item for item in comparison["quotes"] if item["freshness"] == "fresh"]
    if not fresh_quotes:
        raise ValueError("no fresh comparable supplier quote exists; obtain a quote from the last 7 days")
    best = fresh_quotes[0]
    quote = best["quote"]
    total = round(quantity * quote["product_cost"] + quote["shipping_cost"], 2)
    blended_unit_cost = total / quantity
    from .operations import create_order
    order = create_order(db_path, product_title, quantity, blended_unit_cost, currency, best["supplier_id"])
    data = order["data"]
    data.update({"supplier_cost_breakdown": {
        "product_cost_per_unit": quote["product_cost"],
        "shipping_total": quote["shipping_cost"],
        "total_landed_supplier_cost": total,
        "currency": currency.upper(),
        "destination": destination,
        "quote_timestamp": quote["quoted_at"],
        "quote_freshness": best["freshness"],
        "supplier_verification": best["status"],
        "supplier_id": best["supplier_id"],
        "source": "operator-entered supplier quote"
    }})
    with connect(db_path) as conn:
        conn.execute("UPDATE workspace_records SET data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                     (json_dump(data), order["id"]))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
                     ("order.prepared_from_quote", "order", str(order["id"]),
                      json_dump({"supplier_id": best["supplier_id"], "quote_freshness": best["freshness"],
                                 "total_cost": total, "currency": currency.upper()})))
    order["data"] = data
    return {"order": order, "selected_quote": best,
            "approval_required_before_supplier_submission": True,
            "warning": comparison["warning"]}


def record_supplier_performance(db_path, supplier_id, metrics):
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")
    required = ("orders_sample", "on_time_rate", "defect_rate", "response_hours", "dispute_rate")
    if any(key not in metrics for key in required):
        raise ValueError("supplier performance metrics are incomplete")
    sample = metrics["orders_sample"]
    if isinstance(sample, bool) or not isinstance(sample, int) or not 1 <= sample <= 100000:
        raise ValueError("orders_sample must be 1..100000")
    clean = {}
    for key in ("on_time_rate", "defect_rate", "dispute_rate"):
        value = metrics[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(key + " must be between 0 and 100")
        clean[key] = round(float(value), 2)
    response = metrics["response_hours"]
    if isinstance(response, bool) or not isinstance(response, (int, float)) or not math.isfinite(response) or not 0 <= response <= 720:
        raise ValueError("response_hours must be between 0 and 720")
    clean["response_hours"] = round(float(response), 2)
    clean["orders_sample"] = sample
    clean["observed_at"] = datetime.now(timezone.utc).isoformat()
    clean["notes"] = str(metrics.get("notes", ""))[:500]
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='supplier'", (supplier_id,)).fetchone()
        if row is None:
            raise ValueError("supplier not found")
        data = json.loads(row["data_json"])
        data.setdefault("performance_observations", []).append(clean)
        conn.execute("UPDATE workspace_records SET data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                     (json_dump(data), supplier_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
                     ("supplier.performance.recorded", "supplier", str(supplier_id),
                      json_dump({"orders_sample": sample, "observed_at": clean["observed_at"]})))
    return supplier_scorecard(db_path, supplier_id)


def supplier_scorecard(db_path, supplier_id):
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='supplier'", (supplier_id,)).fetchone()
    if row is None:
        raise ValueError("supplier not found")
    data = json.loads(row["data_json"])
    observations = data.get("performance_observations", [])
    if not observations:
        return {"supplier_id": supplier_id, "supplier": row["title"], "score": None,
                "confidence": "no_observations", "sample_size": 0,
                "warning": "No supplier performance data has been recorded."}
    latest = observations[-1]
    punctuality = latest["on_time_rate"]
    quality = 100 - latest["defect_rate"]
    responsiveness = 100 * (1 - latest["response_hours"] / 720)
    dispute_safety = 100 - latest["dispute_rate"]
    score = round(punctuality * .4 + quality * .3 + responsiveness * .15 + dispute_safety * .15, 1)
    sample = latest["orders_sample"]
    confidence = "low" if sample < 10 else "medium" if sample < 50 else "higher"
    return {"supplier_id": supplier_id, "supplier": row["title"], "score": score,
            "components": {"on_time": punctuality, "quality": quality,
                           "responsiveness": round(responsiveness, 1), "dispute_safety": dispute_safety},
            "sample_size": sample, "confidence": confidence, "observed_at": latest["observed_at"],
            "notes": latest.get("notes", ""),
            "warning": "Operator-entered supplier performance; not independently verified. Score is a heuristic, not a guarantee."}
