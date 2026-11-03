"""Safe mock-mode job processor for internal drafting and calculations."""
from .jobs import claim_next, finish, fail
from .commerce import build_design_brief, generate_listing_draft, draft_marketing_content, triage_support_ticket
from .intelligence.economics import Offer, calculate_unit_economics, compare_channels

def process_job(job):
    payload=job["payload"]
    kind=job["kind"]
    if kind=="design.brief":
        result=build_design_brief(**payload)
    elif kind=="listing.draft":
        result=generate_listing_draft(**payload)
    elif kind=="support.triage":
        result=triage_support_ticket(**payload)
    elif kind=="marketing.draft":
        result=draft_marketing_content(**payload)
    elif kind=="economics.calculate":
        result=calculate_unit_economics(Offer(**payload))
    elif kind=="economics.compare":
        result=compare_channels(Offer(**payload["pod"]),Offer(**payload["dropshipping"]))
    else:
        raise ValueError("No safe processor registered for job kind: "+kind)
    return {"mode":"mock","kind":kind,"result":result}

def run_once(db_path):
    job=claim_next(db_path)
    if job is None: return None
    try:
        result=process_job(job)
        finish(db_path,job["id"],result)
        return {"id":job["id"],"status":"succeeded","result":result}
    except Exception as exc:
        fail(db_path,job["id"],str(exc),retry=False)
        return {"id":job["id"],"status":"failed","error":str(exc)}

def run_until_empty(db_path, max_jobs=100):
    outcomes=[]
    for _ in range(max(1,min(int(max_jobs),1000))):
        outcome=run_once(db_path)
        if outcome is None: break
        outcomes.append(outcome)
    return outcomes
