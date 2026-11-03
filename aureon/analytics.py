"""Performance summaries from explicitly supplied campaign observations."""
from .workflows import create_record, list_records

def record_campaign_metrics(db_path,campaign_id,metrics):
    if not isinstance(metrics,dict): raise ValueError("metrics must be an object")
    campaign=next((x for x in list_records(db_path,"campaign",250) if x["id"]==campaign_id),None)
    if not campaign: raise ValueError("campaign not found")
    names=("impressions","clicks","spend","orders","revenue")
    clean={}
    for name in names:
        value=metrics.get(name,0)
        if not isinstance(value,(int,float)) or value<0: raise ValueError(name+" must be non-negative")
        clean[name]=float(value)
    if clean["clicks"]>clean["impressions"]: raise ValueError("clicks cannot exceed impressions")
    if clean["orders"]>clean["clicks"]: raise ValueError("orders cannot exceed clicks")
    data=campaign["data"]; history=data.setdefault("metric_observations",[]); history.append(clean)
    from .db import connect,json_dump
    with connect(db_path) as conn:
        conn.execute("UPDATE workspace_records SET data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(json_dump(data),campaign_id))
    return campaign_metrics(clean)

def campaign_metrics(m):
    spend=m["spend"]; revenue=m["revenue"]
    return {"impressions":int(m["impressions"]),"clicks":int(m["clicks"]),"orders":int(m["orders"]),
      "revenue":round(revenue,2),"spend":round(spend,2),
      "click_through_rate":round(m["clicks"]/m["impressions"],4) if m["impressions"] else 0,
      "conversion_rate":round(m["orders"]/m["clicks"],4) if m["clicks"] else 0,
      "cost_per_order":round(spend/m["orders"],2) if m["orders"] else None,
      "return_on_ad_spend":round(revenue/spend,4) if spend else None,
      "revenue_minus_ad_spend":round(revenue-spend,2),
      "warning":"Revenue minus ad spend is not profit; product, shipping, platform, payment, tax and refund costs are excluded."}

def summarize_campaigns(db_path):
    result=[]
    for campaign in list_records(db_path,"campaign",250):
        observations=campaign["data"].get("metric_observations",[])
        result.append({"id":campaign["id"],"title":campaign["title"],"status":campaign["status"],
          "observations":len(observations),"latest":campaign_metrics(observations[-1]) if observations else None})
    return result
