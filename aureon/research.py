"""Evidence-backed opportunity intake and scoring."""
from datetime import datetime, timezone
from urllib.parse import urlparse
from .intelligence.scoring import score_opportunity
from .workflows import create_record

def validate_evidence(items):
    if not isinstance(items,list) or not items:
        raise ValueError("at least one evidence item is required")
    clean=[]
    for item in items:
        if not isinstance(item,dict): raise ValueError("evidence items must be objects")
        url=item.get("source_url","")
        parsed=urlparse(url)
        if parsed.scheme not in {"http","https"} or not parsed.netloc:
            raise ValueError("evidence source_url must be an http(s) URL")
        collected=item.get("collected_at","")
        try:
            stamp=datetime.fromisoformat(collected.replace("Z","+00:00"))
        except Exception as exc: raise ValueError("collected_at must be an ISO-8601 timestamp") from exc
        if stamp.tzinfo is None: raise ValueError("collected_at must include a timezone")
        clean.append({"source_url":url,"source":str(item.get("source",""))[:100],
          "collected_at":collected,"observation":str(item.get("observation",""))[:1000],
          "metric":str(item.get("metric",""))[:100],"value":item.get("value"),
          "region":str(item.get("region","global"))[:80]})
    return clean

def assess_opportunity(title, evidence, signals, region="global", business_model="undecided"):
    evidence=validate_evidence(evidence)
    scored=score_opportunity(signals)
    if not isinstance(title,str) or not title.strip(): raise ValueError("title is required")
    payload={"evidence":evidence,"signals":scored["input_signals"],"score":scored,
      "region":str(region)[:80],"business_model":business_model,
      "evidence_count":len(evidence),"decision":"review_required"}
    return {"title":title.strip(),"score":scored,"record_payload":payload}

def save_opportunity(db_path,title,evidence,signals,region="global",business_model="undecided"):
    result=assess_opportunity(title,evidence,signals,region,business_model)
    status="shortlisted" if result["score"]["tier"]=="strong_candidate" else "investigate"
    record=create_record(db_path,"opportunity",result["title"],result["record_payload"],status)
    return {"record":record,"assessment":result["score"]}
