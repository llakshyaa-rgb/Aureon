"""Normalized supplier quote records and transparent quote comparisons."""
from datetime import datetime, timezone
from .workflows import create_record, list_records
from .intelligence.economics import Offer, calculate_unit_economics

def add_supplier(db_path,name,provider,product_type,website=None,notes=""):
    if website:
        from urllib.parse import urlparse
        u=urlparse(website)
        if u.scheme not in {"http","https"} or not u.netloc: raise ValueError("website must be an http(s) URL")
    data={"provider":str(provider)[:80],"product_type":str(product_type)[:100],
          "website":website,"notes":str(notes)[:500],"quotes":[],"verification":"unverified"}
    return create_record(db_path,"supplier",name,data,"research")

def add_quote(db_path,supplier_id,quote):
    if not isinstance(quote,dict): raise ValueError("quote must be an object")
    suppliers=[r for r in list_records(db_path,"supplier",250) if r["id"]==supplier_id]
    if not suppliers: raise ValueError("supplier not found")
    required=("product_cost","shipping_cost","currency","destination","quoted_at")
    if any(k not in quote for k in required): raise ValueError("quote missing required fields")
    for key in ("product_cost","shipping_cost"):
        if not isinstance(quote[key],(int,float)) or quote[key]<0: raise ValueError(key+" must be non-negative")
    if len(quote["currency"])!=3: raise ValueError("currency must be a three-letter code")
    try:
        dt=datetime.fromisoformat(quote["quoted_at"].replace("Z","+00:00"))
        if dt.tzinfo is None: raise ValueError()
    except Exception as exc: raise ValueError("quoted_at must be timezone-aware ISO-8601") from exc
    record=suppliers[0]; data=record["data"]
    item={**quote,"currency":quote["currency"].upper(),"product_cost":round(float(quote["product_cost"]),2),
          "shipping_cost":round(float(quote["shipping_cost"]),2),"status":"unverified"}
    data["quotes"].append(item)
    from .workflows import transition_record
    # Update record payload through a safe dedicated helper, retaining status.
    from .db import connect, json_dump
    with connect(db_path) as conn:
        conn.execute("UPDATE workspace_records SET data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                     (json_dump(data),supplier_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
                     ("supplier.quote.added","supplier",str(supplier_id),json_dump({"destination":item["destination"],"currency":item["currency"]})))
    return item

def compare_supplier_quotes(db_path,product_type,destination,currency):
    candidates=[]
    for supplier in list_records(db_path,"supplier",250):
        if supplier["data"].get("product_type","").lower()!=product_type.lower(): continue
        for quote in supplier["data"].get("quotes",[]):
            if quote["destination"].lower()==destination.lower() and quote["currency"]==currency.upper():
                total=round(quote["product_cost"]+quote["shipping_cost"],2)
                candidates.append({"supplier_id":supplier["id"],"supplier":supplier["title"],
                  "provider":supplier["data"].get("provider"),"landed_cost":total,"currency":currency.upper(),
                  "quoted_at":quote["quoted_at"],"status":quote.get("status","unverified"),
                  "quote":quote})
    candidates.sort(key=lambda x:x["landed_cost"])
    return {"quotes":candidates,"best_quote":candidates[0] if candidates else None,
      "warning":"Quotes are user-supplied and unverified. Confirm stock, quality, shipping, taxes and current price with the supplier."}
