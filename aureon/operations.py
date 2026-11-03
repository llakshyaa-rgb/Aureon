"""Order lifecycle simulator; matching approval is mandatory before submission."""
import json,math,re
from .workflows import create_record
from .db import connect,json_dump

def _get_order(conn,order_id):
    row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='order'",(order_id,)).fetchone()
    if row is None: raise ValueError("order not found")
    item=dict(row);item["data"]=json.loads(item.pop("data_json"));return item

def create_order(db_path,product_title,quantity,unit_cost,currency,supplier_id=None,customer_reference=None):
    if not isinstance(product_title,str) or not product_title.strip() or len(product_title)>200: raise ValueError("product_title is required")
    if isinstance(quantity,bool) or not isinstance(quantity,int) or quantity<1 or quantity>10000: raise ValueError("quantity must be 1..10000")
    if isinstance(unit_cost,bool) or not isinstance(unit_cost,(int,float)) or not math.isfinite(unit_cost) or unit_cost<0: raise ValueError("unit_cost must be finite and non-negative")
    if not isinstance(currency,str) or not re.fullmatch(r"[A-Za-z]{3}",currency): raise ValueError("currency must be three-letter code")
    if supplier_id is not None:
        from .workflows import list_records
        if not isinstance(supplier_id,int) or isinstance(supplier_id,bool) or not any(x["id"]==supplier_id for x in list_records(db_path,"supplier",250)):
            raise ValueError("supplier_id must reference an existing supplier")
    data={"product_title":product_title.strip(),"quantity":quantity,"unit_cost":round(float(unit_cost),2),
      "currency":currency.upper(),"supplier_id":supplier_id,"customer_reference":str(customer_reference)[:150] if customer_reference else None,
      "supplier_order_status":"not_submitted","tracking":None,"total_supplier_cost":round(quantity*unit_cost,2)}
    return create_record(db_path,"order","Order: "+product_title.strip(),data,"simulated")

def request_supplier_order_approval(db_path,order_id,reason="Review supplier order before placing"):
    if not isinstance(reason,str) or not reason.strip(): raise ValueError("approval reason is required")
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        order=_get_order(conn,order_id)
        if order["status"] not in {"simulated","awaiting_approval"}: raise ValueError("order is not awaiting supplier approval")
        pending=conn.execute("SELECT id FROM approvals WHERE action='place_supplier_order' AND target_type='order' AND target_id=? AND status='pending'",(str(order_id),)).fetchone()
        if pending: raise ValueError("this order already has a pending approval")
        cur=conn.execute("INSERT INTO approvals(action,target_type,target_id,amount,currency,reason) VALUES(?,?,?,?,?,?)",
          ("place_supplier_order","order",str(order_id),order["data"]["total_supplier_cost"],order["data"]["currency"],reason.strip()[:1000]))
        approval=dict(conn.execute("SELECT * FROM approvals WHERE id=?",(cur.lastrowid,)).fetchone())
        conn.execute("UPDATE workspace_records SET status='awaiting_approval',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(order_id,))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
          ("order.approval_requested","order",str(order_id),json_dump({"approval_id":approval["id"]})))
        return _get_order(conn,order_id),approval

def record_supplier_submission(db_path,order_id,approval_id,supplier_order_reference):
    if not isinstance(supplier_order_reference,str) or not supplier_order_reference.strip(): raise ValueError("supplier_order_reference is required")
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        order=_get_order(conn,order_id)
        if order["status"]!="awaiting_approval" or order["data"].get("supplier_order_status")!="not_submitted":
            raise ValueError("order is not awaiting first supplier submission")
        approval=conn.execute("SELECT * FROM approvals WHERE id=?",(approval_id,)).fetchone()
        if approval is None or approval["status"]!="approved" or approval["action"]!="place_supplier_order" or approval["target_type"]!="order" or approval["target_id"]!=str(order_id):
            raise ValueError("a matching approved supplier-order approval is required")
        if approval["amount"] is None or round(float(approval["amount"]),2)!=round(float(order["data"]["total_supplier_cost"]),2) or approval["currency"]!=order["data"]["currency"]:
            raise ValueError("approval amount or currency does not match this order")
        data=order["data"];data["supplier_order_status"]="submitted";data["supplier_order_reference"]=supplier_order_reference.strip()[:150]
        conn.execute("UPDATE approvals SET status='consumed' WHERE id=? AND status='approved'",(approval_id,))
        conn.execute("UPDATE workspace_records SET data_json=?,status='approved',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
          (json_dump(data),order_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
          ("order.supplier_submitted","order",str(order_id),json_dump({"approval_id":approval_id,"simulated":True})))
        return _get_order(conn,order_id)

def update_tracking(db_path,order_id,tracking_code,fulfillment_status):
    allowed={"in_production":{"shipped","delayed","cancelled"},"shipped":{"delivered","delayed"},"delayed":{"in_production","shipped","delivered","cancelled"}}
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        order=_get_order(conn,order_id);data=order["data"]
        if data.get("supplier_order_status")!="submitted": raise ValueError("cannot update fulfillment before approved supplier submission")
        current=data.get("fulfillment_status")
        if fulfillment_status not in allowed.get(current,{"in_production","cancelled"}): raise ValueError("invalid fulfillment status transition")
        if fulfillment_status in {"shipped","delivered"} and (not isinstance(tracking_code,str) or not tracking_code.strip()):
            raise ValueError("tracking code is required for shipped or delivered orders")
        data["tracking"]=tracking_code.strip()[:200] if isinstance(tracking_code,str) and tracking_code.strip() else data.get("tracking")
        data["fulfillment_status"]=fulfillment_status
        status="fulfilled" if fulfillment_status=="delivered" else "cancelled" if fulfillment_status=="cancelled" else "approved"
        conn.execute("UPDATE workspace_records SET data_json=?,status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
          (json_dump(data),status,order_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
          ("order.fulfillment_updated","order",str(order_id),json_dump({"status":fulfillment_status})))
        return _get_order(conn,order_id)

def request_refund_review(db_path,order_id,amount,reason):
    if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount<=0:
        raise ValueError("refund amount must be positive and finite")
    if not isinstance(reason,str) or not reason.strip(): raise ValueError("refund reason is required")
    with connect(db_path) as conn:
        order=_get_order(conn,order_id)
        if order["status"] not in {"approved","fulfilled"}: raise ValueError("only submitted orders can be reviewed for refund")
        if amount>order["data"]["total_supplier_cost"]: raise ValueError("refund exceeds recorded supplier cost")
        cur=conn.execute("INSERT INTO approvals(action,target_type,target_id,amount,currency,reason) VALUES(?,?,?,?,?,?)",
          ("issue_refund","order",str(order_id),round(float(amount),2),order["data"]["currency"],reason.strip()[:1000]))
        return dict(conn.execute("SELECT * FROM approvals WHERE id=?",(cur.lastrowid,)).fetchone())
