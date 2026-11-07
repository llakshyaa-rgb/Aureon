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
 elif kind=="commerce.mission":
  if db_path is None:raise ValueError("database path required")
  from .missions import run_mission
  result=run_mission(db_path,payload)
 elif kind=="agent.run":
  if db_path is None:raise ValueError("database path required")
  plan_payload=payload.get("plan")
  if not isinstance(plan_payload,dict) or not isinstance(plan_payload.get("tasks"),list):raise ValueError("agent plan is invalid")
  from .agents import plan_run
  from .db import connect,json_dump
  import json
  plan=plan_run(plan_payload.get("name"),plan_payload["tasks"])
  run_id=payload.get("run_id")
  outputs=[None]*len(plan["tasks"])
  states=["pending"]*len(plan["tasks"])
  warnings=[]
  progress=[]
  if run_id is not None:
   with connect(db_path) as conn:
    saved=conn.execute("SELECT data_json FROM workspace_records WHERE id=? AND kind='agent_run'",(run_id,)).fetchone()
    if saved:
     prior=json.loads(saved["data_json"])
     saved_states=prior.get("step_states",[])
     saved_outputs=prior.get("step_outputs",[])
     for i in range(min(len(states),len(saved_states))):
      if saved_states[i]=="succeeded" and i<len(saved_outputs):
       states[i]="succeeded";outputs[i]=saved_outputs[i]
      elif saved_states[i] in {"failed","skipped"}:
       states[i]=saved_states[i]
      elif saved_states[i]=="running":
       states[i]="failed"
       warnings.append("Step "+str(i)+" was interrupted while running; it was not replayed automatically to avoid duplicate side effects.")
     warnings.extend(x for x in prior.get("warnings",[]) if x not in warnings)
     progress=list(prior.get("progress",[]))
  def persist(step_index,state,error=None):
   item={"step":step_index,"kind":plan["tasks"][step_index]["kind"],"status":state}
   if error:item["error"]=str(error)[:500]
   progress.append(item)
   if run_id is not None:
    with connect(db_path) as conn:
     row=conn.execute("SELECT data_json FROM workspace_records WHERE id=? AND kind='agent_run'",(run_id,)).fetchone()
     if row:
      data=json.loads(row["data_json"])
      data["progress"]=list(progress)
      data["step_states"]=list(states)
      data["step_outputs"]=list(outputs)
      data["current_step"]=plan["tasks"][step_index]["kind"] if state=="running" else None
      data["completed_steps"]=sum(x in {"succeeded","failed","skipped"} for x in states)
      data["warnings"]=list(warnings)
      conn.execute("UPDATE workspace_records SET status=?,data_json=? WHERE id=?",
       ("running" if state in {"running","succeeded","skipped"} else "needs_attention",json_dump(data),run_id))
  def resolve(value):
   if isinstance(value,dict) and set(value)=={"$from","path"}:
    index=value["$from"]
    if isinstance(index,bool) or not isinstance(index,int) or index<0 or index>=len(outputs) or states[index]!="succeeded":
     raise ValueError("referenced dependency output is unavailable")
    current=outputs[index]
    for part in value["path"].split("."):
     if isinstance(current,dict) and part in current:current=current[part]
     else:raise ValueError("agent output reference path does not exist: "+value["path"])
    return current
   if isinstance(value,dict):return {k:resolve(v) for k,v in value.items()}
   if isinstance(value,list):return [resolve(v) for v in value]
   return value
  for step in plan["tasks"]:
   idx=step["step"]
   if states[idx] in {"succeeded","failed","skipped"}:
    continue
   if any(states[dep]!="succeeded" for dep in step.get("depends_on",[])):
    states[idx]="skipped"
    warnings.append("Step "+str(idx)+" skipped because a dependency failed.")
    persist(idx,"skipped")
    continue
   persist(idx,"running")
   try:
    task_payload=resolve(step["payload"])
    output=process_job({"kind":step["kind"],"payload":task_payload},db_path)
    outputs[idx]=output
    states[idx]="succeeded"
    persist(idx,"succeeded")
   except Exception as exc:
    states[idx]="failed"
    warnings.append("Step "+str(idx)+" ("+step["kind"]+"): "+str(exc)[:500])
    persist(idx,"failed",exc)
  results=[{"step":i,"kind":plan["tasks"][i]["kind"],"status":states[i],
            **({"output":outputs[i]} if states[i]=="succeeded" else {})}
           for i in range(len(states))]
  overall="succeeded" if all(x=="succeeded" for x in states) else "completed_with_warnings" if any(x=="succeeded" for x in states) else "failed"
  result={"run_name":plan.get("name"),"steps":results,"status":overall,"warnings":warnings}
  if run_id is not None:
   with connect(db_path) as conn:
    row=conn.execute("SELECT data_json FROM workspace_records WHERE id=? AND kind='agent_run'",(run_id,)).fetchone()
    if row:
     data=json.loads(row["data_json"]);data["current_step"]=None;data["progress_status"]=overall;data["warnings"]=warnings
     data["step_states"]=list(states);data["step_outputs"]=list(outputs)
     data["completed_steps"]=sum(x in {"succeeded","failed","skipped"} for x in states)
     conn.execute("UPDATE workspace_records SET status=?,data_json=? WHERE id=?",
      ("completed" if overall=="succeeded" else "completed_with_warnings" if overall=="completed_with_warnings" else "failed",json_dump(data),run_id))

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
  retryable=job["kind"] not in {"agent.run","commerce.mission"} and isinstance(exc,RuntimeError) and job["attempts"]<job["max_attempts"]
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
    from .backups import backup_if_due
    initialize_workspace(db_path)
    initialize_scheduler(db_path)
    while not stop_event.is_set():
        try:
            backup = backup_if_due(db_path)
            if backup["created"]:
                print("[backup] verified snapshot:", backup["path"])
            enqueue_due(db_path)
            run_once(db_path)
        except Exception as exc:
            print("[worker] background cycle failed:", str(exc))
        stop_event.wait(max(1, min(float(interval), 60)))
