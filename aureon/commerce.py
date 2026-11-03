"""Deterministic commerce drafting services; no external calls or claims of live AI."""
import re
from .workflows import create_record

def _clean(value, limit=500):
    if not isinstance(value,str) or not value.strip():
        raise ValueError("required text field is missing")
    return re.sub(r"\s+"," ",value).strip()[:limit]

def build_design_brief(niche, audience, product_type, style, concept, constraints=None):
    brief={
      "niche":_clean(niche,120),"audience":_clean(audience,200),
      "product_type":_clean(product_type,120),"style":_clean(style,160),
      "concept":_clean(concept,500),"constraints":constraints or [],
      "originality_check_required":True,"trademark_review_required":True,
      "print_validation_required":True,
      "prompt":"Create an original "+_clean(style,100)+" design about "+_clean(concept,250)+
        " for "+_clean(audience,150)+". Product: "+_clean(product_type,100)+
        ". Avoid existing characters, logos, brands, copied compositions and protected slogans."
    }
    return brief

def create_design_brief(path, **kwargs):
    brief=build_design_brief(**kwargs)
    return create_record(path,"design",brief["concept"],brief,"brief")

def generate_listing_draft(product, audience, keywords, brand_voice="clear and helpful"):
    if not isinstance(product,dict): raise ValueError("product must be an object")
    title=_clean(product.get("title"),180)
    audience=_clean(audience,180)
    if not isinstance(keywords,list) or not keywords: raise ValueError("keywords must be a non-empty list")
    terms=[]
    for word in keywords:
        term=_clean(word,80)
        if term.lower() not in [x.lower() for x in terms]: terms.append(term)
    description=(title+" is designed for "+audience+". "+_clean(product.get("features","A thoughtfully designed product."),500)+
      " Made for people who appreciate "+", ".join(terms[:5])+".")
    return {"title":title[:140],"description":description,"tags":terms[:13],
      "audience":audience,"brand_voice":_clean(brand_voice,100),
      "alt_text":"Product image of "+title,"status":"draft",
      "review_required":["Verify all product claims","Confirm supplier specifications and print areas",
                         "Check trademark and copyright risks","Verify shipping and return policy"]}

def create_listing(path, product, audience, keywords, brand_voice="clear and helpful"):
    listing=generate_listing_draft(product,audience,keywords,brand_voice)
    return create_record(path,"listing",listing["title"],listing,"draft")

def draft_marketing_content(product_title, audience, channel, benefit, call_to_action):
    channel=_clean(channel,50).lower()
    if channel not in {"instagram","tiktok","pinterest","email","facebook"}:
        raise ValueError("unsupported draft channel")
    title=_clean(product_title,150); audience=_clean(audience,150)
    benefit=_clean(benefit,250); cta=_clean(call_to_action,120)
    return {"channel":channel,"copy":benefit+" — created with "+audience+" in mind. "+title+". "+cta,
      "status":"draft","requires_human_review":True,
      "checks":["Verify claims and product availability","Check platform policies","Do not publish or spend automatically"]}

def triage_support_ticket(subject, message, order_status=None):
    subject=_clean(subject,180); message=_clean(message,2000)
    text=(subject+" "+message).lower()
    if any(k in text for k in ("chargeback","fraud","lawyer","legal","unsafe","injury","allergic")):
        category="urgent_escalation"; priority="urgent"
    elif any(k in text for k in ("refund","return","cancel","money back")):
        category="refund_or_cancellation"; priority="high"
    elif any(k in text for k in ("late","tracking","where is my","delivery","shipping")):
        category="shipping_status"; priority="normal"
    else: category="general_product_question"; priority="normal"
    return {"subject":subject,"category":category,"priority":priority,
      "order_status":order_status,"draft_reply":"Thanks for reaching out. We’re checking the details and will follow up with verified information.",
      "human_review_required":True,"no_refund_or_delivery_promise":True}

def create_support_ticket(path, subject, message, order_status=None):
    result=triage_support_ticket(subject,message,order_status)
    return create_record(path,"support_ticket",result["subject"],result,"escalated" if result["priority"]=="urgent" else "open")

def summarize_performance(finance, records):
    summary={"finance_by_currency":finance,"record_counts":{},"notes":[
      "Only recorded entries are included; missing provider data is not inferred.",
      "Estimated and actual finance entries remain separate.",
      "This is an operational snapshot, not an attribution model."]}
    for row in records: summary["record_counts"][row["kind"]]=summary["record_counts"].get(row["kind"],0)+1
    return summary
