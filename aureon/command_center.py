"""Read-only command center snapshot and safe, non-executing command parser."""
import re
from .workflows import list_records,list_approvals,finance_summary
from .jobs import list_jobs
from .scheduler import list_scheduled
from .agents import runtime_status
def dashboard_snapshot(db_path):
 records=list_records(db_path,None,250);counts={}
 for r in records:counts[r["kind"]]=counts.get(r["kind"],0)+1
 approvals=list_approvals(db_path)
 return {"mode":"mock","records":counts,"pending_approvals":sum(a["status"]=="pending" for a in approvals),
 "approvals":approvals[:20],"jobs":list_jobs(db_path,30),"finance":finance_summary(db_path),
 "schedules":list_scheduled(db_path)[:30],"agents":runtime_status(db_path),"recent_records":records[:30],
 "safety":{"localhost_only":True,"publishing_enabled":False,"supplier_orders_enabled":False,"ad_spend_enabled":False}}
def interpret_command(command):
 if not isinstance(command,str) or not command.strip() or len(command)>500:raise ValueError("command must be 1-500 characters")
 raw=command.strip()
 patterns=[(r"^(?:draft|create) (?:a )?design brief for (.+)$","design.brief"),
 (r"^(?:triage|review) support ticket (.+)$","support.triage"),
 (r"^(?:draft|create) marketing copy for (.+)$","marketing.draft")]
 for pattern,kind in patterns:
  m=re.match(pattern,raw,re.I)
  if m:return {"recognized":True,"kind":kind,"subject":m.group(1),"needs_payload_fields":True,"submitted":False}
 return {"recognized":False,"submitted":False,"message":"No safe command match. Arbitrary natural-language text is never executed."}
