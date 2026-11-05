"""Local worker for persistent, non-publishing commerce workflows."""
from .jobs import claim_next,finish,fail
from .commerce import build_design_brief,generate_listing_draft,draft_marketing_content,triage_support_ticket
from .intelligence.economics import Offer,calculate_unit_economics,compare_channels
from .research import save_opportunity
from .analytics import campaign_metrics,record_campaign_metrics
from .workflows import create_record,initialize_workspace
from .trends import collect_trends
def process_job(job,db_path=None):
 payload=job["payload"];kind=job["kind"]
 if kind=="design.brief":
  result=build_design_brief(**payload)
  if db_path is not None:result={"draft":result,"record":create_record(db_path,"design",payload.get("concept","Design brief"),result,"brief")}
 elif kind=="listing.draft":
  result=generate_listing_draft(**payload)
  if db_path is not None:result={"draft":result,"record":create_record(db_path,"listing",payload.get("product",{}).get("title","Listing draft"),result,"draft")}
 elif kind=="support.triage":
  result=triage_support_ticket(**payload)
  if db_path is not None:result={"triage":result,"record":create_record(db_path,"support_ticket",payload.get("subject","Support ticket"),result,"escalated" if result["priority"]=="urgent" else "drafted")}
 elif kind=="marketing.draft":
  result=draft_marketing_content(**payload)
  if db_path is not None:result={"draft":result,"record":create_record(db_path,"campaign",payload.get("campaign_name",payload.get("product_title","Marketing draft")),{"draft":result},"draft")}
 elif kind=="economics.calculate":result=calculate_unit_economics(Offer(**payload))
 elif kind=="economics.compare":result=compare_channels(Offer(**payload["pod"]),Offer(**payload["dropshipping"]))
 elif kind=="opportunity.assess":
  if db_path is None:raise ValueError("database path required")
  result=save_opportunity(db_path,**payload)
 elif kind=="campaign.metrics":
  if db_path is not None and "campaign_id" in payload:result=record_campaign_metrics(db_path,payload["campaign_id"],payload["metrics"])
  else:result=campaign_metrics(payload.get("metrics",payload))
 elif kind=="trends.collect":
  if db_path is None:raise ValueError("database path required")
  result=collect_trends(db_path,payload.get("geo","IN"),payload.get("limit",25))
 elif kind=="product.create":
  if db_path is None:raise ValueError("database path required")
  result=create_record(db_path,"product",payload["title"],payload.get("data",{}),"draft")
 else:raise ValueError("No safe processor registered for job kind: "+kind)
 return {"mode":"local","kind":kind,"result":result}
def run_once(db_path):
 initialize_workspace(db_path)
 job=claim_next(db_path)
 if job is None:return None
 try:
  result=process_job(job,db_path);finish(db_path,job["id"],result)
  return {"id":job["id"],"status":"succeeded","result":result}
 except Exception as exc:
  fail(db_path,job["id"],str(exc),retry=isinstance(exc, RuntimeError))
  return {"id":job["id"],"status":"failed","error":str(exc)}
def run_until_empty(db_path,max_jobs=100):
 outcomes=[]
 for _ in range(max(1,min(int(max_jobs),1000))):
  outcome=run_once(db_path)
  if outcome is None:break
  outcomes.append(outcome)
 return outcomes


def background_loop(db_path, stop_event, interval=3):
    """Process local jobs and due schedules while the dashboard server is running."""
    import time
    from .scheduler import initialize_scheduler, enqueue_due
    initialize_workspace(db_path)
    initialize_scheduler(db_path)
    while not stop_event.is_set():
        try:
            enqueue_due(db_path)
            run_once(db_path)
        except Exception as exc:
            print("[worker] background cycle failed:", str(exc))
        stop_event.wait(max(1, min(float(interval), 60)))
