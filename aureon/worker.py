"""Safe mock-mode job processor for internal workflows and calculations."""
from .jobs import claim_next, finish, fail
from .commerce import build_design_brief, generate_listing_draft, draft_marketing_content, triage_support_ticket
from .intelligence.economics import Offer, calculate_unit_economics, compare_channels
from .research import assess_opportunity
from .analytics import campaign_metrics
from .workflows import create_record

def process_job(job, db_path=None):
    payload=job["payload"]; kind=job["kind"]
    if kind=="design.brief": result=build_design_brief(**payload)
    elif kind=="listing.draft": result=generate_listing_draft(**payload)
    elif kind=="support.triage": result=triage_support_ticket(**payload)
    elif kind=="marketing.draft": result=draft_marketing_content(**payload)
    elif kind=="economics.calculate": result=calculate_unit_economics(Offer(**payload))
    elif kind=="economics.compare": result=compare_channels(Offer(**payload["pod"]),Offer(**payload["dropshipping"]))
    elif kind=="opportunity.assess": result=assess_opportunity(**payload)
    elif kind=="campaign.metrics": result=campaign_metrics(payload)
    elif kind=="product.create":
        if db_path is None: raise ValueError("database path required")
        result=create_record(db_path,"product",payload["title"],payload.get("data",{}),"draft")
    else: raise ValueError("No safe processor registered for job kind: "+kind)
    return {"mode":"mock","kind":kind,"result":result}

def run_once(db_path):
    job=claim_next(db_path)
    if job is None: return None
    try:
        result=process_job(job,db_path)
        finish(db_path,job["id"],result)
        return {"id":job["id"],"status":"succeeded","result":result}
    except Exception as exc:
        fail(db_path,job["id"],str(exc),retry=False)
        return {"id":job["id"],"status":"failed","error":str(exc)}

def run_until_empty(db_path,max_jobs=100):
    outcomes=[]
    for _ in range(max(1,min(int(max_jobs),1000))):
        outcome=run_once(db_path)
        if outcome is None: break
        outcomes.append(outcome)
    return outcomes
