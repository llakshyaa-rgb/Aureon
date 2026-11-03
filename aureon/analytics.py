"""Campaign observation storage and transparent performance calculations."""
import math,re
from datetime import datetime,timezone
from .workflows import list_records
def campaign_metrics(metrics):
 if not isinstance(metrics,dict):raise ValueError("metrics must be an object")
 clean={}
 for name in ("impressions","clicks","spend","orders","revenue"):
  value=metrics.get(name,0)
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError(name+" must be finite and non-negative")
  clean[name]=float(value)
 if clean["impressions"]%1 or clean["clicks"]%1 or clean["orders"]%1:raise ValueError("impressions, clicks and orders must be whole numbers")
 if clean["clicks"]>clean["impressions"]:raise ValueError("clicks cannot exceed impressions")
 if clean["orders"]>clean["clicks"]:raise ValueError("orders cannot exceed clicks")
 spend,revenue=clean["spend"],clean["revenue"]
 return {"impressions":int(clean["impressions"]),"clicks":int(clean["clicks"]),"orders":int(clean["orders"]),
 "revenue":round(revenue,2),"spend":round(spend,2),
 "click_through_rate":round(clean["clicks"]/clean["impressions"],4) if clean["impressions"] else 0,
 "conversion_rate":round(clean["orders"]/clean["clicks"],4) if clean["clicks"] else 0,
 "cost_per_order":round(spend/clean["orders"],2) if clean["orders"] else None,
 "return_on_ad_spend":round(revenue/spend,4) if spend else None,
 "revenue_minus_ad_spend":round(revenue-spend,2),
 "warning":"Revenue minus ad spend is not profit; product, shipping, platform, payment, tax and refund costs are excluded."}
def record_campaign_metrics(db_path,campaign_id,metrics):
 computed=campaign_metrics(metrics)
 currency=metrics.get("currency","USD")
 if not isinstance(currency,str) or not re.fullmatch(r"[A-Za-z]{3}",currency):raise ValueError("currency must be a three-letter code")
 from .db import connect,json_dump
 with connect(db_path) as conn:
  conn.execute("BEGIN IMMEDIATE")
  row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='campaign'",(campaign_id,)).fetchone()
  if row is None:raise ValueError("campaign not found")
  import json
  data=json.loads(row["data_json"]);history=data.setdefault("metric_observations",[])
  if not isinstance(history,list):raise ValueError("campaign metric history is corrupted")
  normalized=currency.upper()
  if history and history[-1].get("currency",normalized)!=normalized:raise ValueError("campaign observations must use one currency")
  observation={**computed,"observed_at":datetime.now(timezone.utc).isoformat(),"currency":normalized}
  history.append(observation)
  conn.execute("UPDATE workspace_records SET data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(json_dump(data),campaign_id))
  conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",("campaign.metrics.recorded","campaign",str(campaign_id),json_dump({"observed_at":observation["observed_at"],"currency":normalized})))
 return observation
def summarize_campaigns(db_path):
 result=[]
 for campaign in list_records(db_path,"campaign",250):
  observations=campaign["data"].get("metric_observations",[])
  result.append({"id":campaign["id"],"title":campaign["title"],"status":campaign["status"],"observations":len(observations),"latest":observations[-1] if observations else None})
 return result
