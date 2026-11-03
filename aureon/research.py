"""Evidence-backed opportunity intake, validation and scoring."""
import math
from datetime import datetime
from urllib.parse import urlparse
from .intelligence.scoring import score_opportunity
from .workflows import create_record

def validate_evidence(items):
    if not isinstance(items,list) or not items:
        raise ValueError("at least one evidence item is required")
    clean=[]; seen=set()
    for item in items:
        if not isinstance(item,dict): raise ValueError("evidence items must be objects")
        url=item.get("source_url")
        if not isinstance(url,str): raise ValueError("source_url must be a string")
        parsed=urlparse(url)
        if parsed.scheme not in {"http","https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("evidence source_url must be a valid public http(s) URL")
        if url in seen: continue
        seen.add(url)
        collected=item.get("collected_at")
        if not isinstance(collected,str): raise ValueError("collected_at must be an ISO-8601 timestamp")
        try:
            stamp=datetime.fromisoformat(collected.replace("Z","+00:00"))
            if stamp.tzinfo is None: raise ValueError()
        except Exception as exc: raise ValueError("collected_at must include a timezone") from exc
        clean.append({"source_url":url,"source":str(item.get("source",""))[:100],
          "collected_at":collected,"observation":str(item.get("observation",""))[:1000],
          "metric":str(item.get("metric",""))[:100],"value":item.get("value"),
          "region":str(item.get("region","global"))[:80]})
    if not clean: raise ValueError("at least one unique evidence URL is required")
    return clean

def assess_opportunity(title,evidence,signals,region="global",business_model="undecided"):
    if not isinstance(title,str) or not title.strip() or len(title)>200: raise ValueError("title must be 1-200 characters")
    if not isinstance(region,str) or not region.strip(): raise ValueError("region is required")
    if not isinstance(business_model,str) or not business_model.strip(): raise ValueError("business_model is required")
    evidence=validate_evidence(evidence)
    scored=score_opportunity(signals)
    payload={"evidence":evidence,"signals":scored["input_signals"],"score":scored,
      "region":region.strip()[:80],"business_model":business_model.strip()[:50],
      "evidence_count":len(evidence),"decision":"review_required"}
    return {"title":title.strip(),"score":scored,"record_payload":payload}

def save_opportunity(db_path,title,evidence,signals,region="global",business_model="undecided"):
    result=assess_opportunity(title,evidence,signals,region,business_model)
    status="shortlisted" if result["score"]["tier"]=="strong_candidate" else "investigate"
    record=create_record(db_path,"opportunity",result["title"],result["record_payload"],status)
    return {"record":record,"assessment":result["score"]}
