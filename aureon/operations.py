"""Order lifecycle simulator with mandatory approval before supplier commitment."""
from .workflows import create_record, list_records, request_approval, list_approvals, transition_record
from .db import connect, json_dump

def create_order(db_path,product_title,quantity,unit_cost,currency,supplier_id=None,customer_reference=None):
    if not isinstance(quantity,int) or quantity<1 or quantity>10000: raise ValueError("quantity must be 1..10000")
    if not isinstance(unit_cost,(int,float)) or unit_cost<0: raise ValueError("unit_cost must be non-negative")
    if not isinstance(currency,str) or len(currency)!=3: raise ValueError("currency must be three-letter code")
    data={"product_title":product_title,"quantity":quantity,"unit_cost":round(float(unit_cost),2),
      "currency":currency.upper(),"supplier_id":supplier_id,"customer_reference":customer_reference,
      "supplier_order_status":"not_submitted","tracking":None,"total_supplier_cost":round(quantity*unit_cost,2)}
    return create_record(db_path,"order","Order: "+str(product_title),data,"simulated")

def request_supplier_order_approval(db_path,order_id,reason="Review supplier order before placing"):
    order=next((x for x in list_records(db_path,"order",250) if x["id"]==order_id),None)
    if not order: raise ValueError("order not found")
    if order["status"] not in {"simulated","awaiting_approval"}: raise ValueError("order is not awaiting supplier approval")
    approval=request_approval(db_path,"place_supplier_order","order",str(order_id),reason,
      order["data"]["total_supplier_cost"],order["data"]["currency"])
    return transition_record(db_path,order_id,"awaiting_approval"),approval

def record_supplier_submission(db_path,order_id,approval_id,supplier_order_reference):
    order=next((x for x in list_records(db_path,"order",250) if x["id"]==order_id),None)
    if not order: raise ValueError("order not found")
    approvals=[a for a in list_approvals(db_path) if a["id"]==approval_id]
    if not approvals or approvals[0]["status"]!="approved" or approvals[0]["action"]!="place_supplier_order" or approvals[0]["target_id"]!=str(order_id):
        raise ValueError("a matching approved supplier-order approval is required")
    data=order["data"]; data["supplier_order_status"]="submitted"; data["supplier_order_reference"]=str(supplier_order_reference)[:150]
    with connect(db_path) as conn:
        conn.execute("UPDATE workspace_records SET data_json=?,status='approved',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
          (json_dump(data),order_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
          ("order.supplier_submitted","order",str(order_id),json_dump({"approval_id":approval_id})))
    return next(x for x in list_records(db_path,"order",250) if x["id"]==order_id)

def update_tracking(db_path,order_id,tracking_code,fulfillment_status):
    if fulfillment_status not in {"in_production","shipped","delivered","delayed","cancelled"}:
        raise ValueError("invalid fulfillment status")
    order=next((x for x in list_records(db_path,"order",250) if x["id"]==order_id),None)
    if not order: raise ValueError("order not found")
    if order["data"].get("supplier_order_status")!="submitted":
        raise ValueError("cannot update fulfillment before approved supplier submission")
    data=order["data"]; data["tracking"]=str(tracking_code)[:200] if tracking_code else None
    data["fulfillment_status"]=fulfillment_status
    with connect(db_path) as conn:
        conn.execute("UPDATE workspace_records SET data_json=?,status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
          (json_dump(data),"fulfilled" if fulfillment_status=="delivered" else "approved",order_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
          ("order.fulfillment_updated","order",str(order_id),json_dump({"status":fulfillment_status})))
    return next(x for x in list_records(db_path,"order",250) if x["id"]==order_id)
