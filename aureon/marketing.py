"""Campaign drafting and approval workflow; never publishes or spends."""
from .commerce import draft_marketing_content
from .workflows import create_record,list_records,request_approval
from .db import connect
import json
def create_campaign(db_path,name,product_title,audience,channel,benefit,call_to_action,budget=None,currency="USD"):
 draft=draft_marketing_content(product_title,audience,channel,benefit,call_to_action)
 if budget is not None and (isinstance(budget,bool) or not isinstance(budget,(int,float)) or budget<0):raise ValueError("budget must be non-negative")
 if not isinstance(currency,str) or len(currency)!=3 or not currency.isalpha():raise ValueError("currency must be three letters")
 data={"product_title":product_title,"audience":audience,"channel":draft["channel"],"draft":draft,
 "budget_estimate":round(float(budget),2) if budget is not None else None,"currency":currency.upper(),
 "publication_status":"draft_only","spend_status":"not_authorized","metric_observations":[]}
 return create_record(db_path,"campaign",name,data,"draft")
def request_campaign_approval(db_path,campaign_id,action,amount=None,reason="Human review required"):
 if action not in {"publish_listing","spend_on_ads"}:raise ValueError("unsupported campaign action")
 with connect(db_path) as conn:
  row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='campaign'",(campaign_id,)).fetchone()
 if row is None:raise ValueError("campaign not found")
 data=json.loads(row["data_json"])
 if action=="spend_on_ads":
  amount=data.get("budget_estimate") if amount is None else amount
  if amount is None:raise ValueError("explicit ad budget required")
  return request_approval(db_path,action,"campaign",campaign_id,reason,amount,data["currency"])
 return request_approval(db_path,action,"campaign",campaign_id,reason)
def campaign_overview(db_path):
 return [{"id":r["id"],"name":r["title"],"status":r["status"],"channel":r["data"].get("channel"),
 "budget_estimate":r["data"].get("budget_estimate"),"currency":r["data"].get("currency"),
 "publication_status":r["data"].get("publication_status"),"spend_status":r["data"].get("spend_status")}
 for r in list_records(db_path,"campaign",250)]
