"""Local worker for persistent, non-publishing commerce workflows."""
from .jobs import claim_next,finish,fail
from .commerce import build_design_brief,generate_listing_draft,draft_marketing_content,triage_support_ticket
from .creative import create_asset,generate_vector_artwork,create_collection
from .intelligence.product_research import analyze_competition
from .intelligence.scenarios import pricing_scenarios
from .intelligence.evaluation import evaluate_product_opportunity
from .intelligence.economics import Offer,calculate_unit_economics,compare_channels
from .research import save_opportunity
from .analytics import campaign_metrics,record_campaign_metrics
from .workflows import create_record,initialize_workspace
from .trends import collect_trends
from .suppliers import prepare_order_from_best_quote
def process_job(job,db_path=None):
 payload=job["payload"];kind=job["kind"]
 if kind=="design.brief":
  result=build_design_brief(**payload)
  if db_path is not None:result={"draft":result,"record":create_record(db_path,"design",payload.get("concept","Design brief"),result,"brief")}
 elif kind=="creative.generate":
  result=create_asset(db_path,**payload) if db_path is not None else generate_vector_artwork(**payload)
 elif kind=="creative.collection":
  if db_path is None:raise ValueError("database path required")
  result=create_collection(db_path,**payload)
 elif kind=="research.competitors":result=analyze_competition(payload["observations"])
 elif kind=="opportunity.evaluate":
  if db_path is None:raise ValueError("database path required")
  result=evaluate_product_opportunity(db_path,**payload)
 elif kind=="supplier.order.prepare":
  if db_path is None:raise ValueError("database path required")
  result=prepare_order_from_best_quote(db_path,**payload)
 elif kind=="economics.scenarios":
  result=pricing_scenarios(Offer(**payload["offer"]),payload.get("prices"),payload.get("target_margin",0.25))
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
 elif kind=="agent.run":
  if db_path is None:raise ValueError("database path required")
  plan=payload.get("plan")
  if not isinstance(plan,dict) or not isinstance(plan.get("tasks"),list):raise ValueError("agent plan is invalid")
  from .agents import plan_run
  plan=plan_run(plan.get("name"),plan["tasks"])
  outputs=[]
  def resolve(value):
   if isinstance(value,dict) and set(value)=={"$from","path"}:
    step=value["$from"]
    if isinstance(step,bool) or not isinstance(step,int) or step<0 or step>=len(outputs):raise ValueError("agent output reference is unavailable")
    current=outputs[step]
    for part in value["path"].split("."):
     if isinstance(current,dict) and part in current:current=current[part]
     else:raise ValueError("agent output reference path does not exist: "+value["path"])
    return current
   if isinstance(value,dict):return {k:resolve(v) for k,v in value.items()}
   if isinstance(value,list):return [resolve(v) for v in value]
   return value
  for step in plan["tasks"]:
   if any(dep>=len(outputs) for dep in step.get("depends_on",[])):raise ValueError("agent dependency did not complete")
   outputs.append(process_job({"kind":step["kind"],"payload":resolve(step["payload"])},db_path))
  result={"run_name":plan.get("name"),"steps":[{"step":i,"kind":plan["tasks"][i]["kind"],"status":"succeeded","output":out} for i,out in enumerate(outputs)],"status":"succeeded"}
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
  retryable=job["kind"]!="agent.run" and isinstance(exc,RuntimeError) and job["attempts"]<job["max_attempts"]
  fail(db_path,job["id"],str(exc),retry=retryable)
  return {"id":job["id"],"status":"retrying" if retryable else "failed","error":str(exc)}
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
