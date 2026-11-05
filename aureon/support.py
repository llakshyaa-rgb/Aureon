"""Persistent customer-support tickets and human-reviewed response drafts."""
from .commerce import triage_support_ticket
from .workflows import create_record,list_records
from .db import connect,json_dump
import json
def _find_order_context(db_path, reference):
 if reference is None or reference=="":
  return None
 if isinstance(reference, bool) or not isinstance(reference, (str, int)) or len(str(reference)) > 150:
  raise ValueError("order_reference must be text or an order ID")
 with connect(db_path) as conn:
  row=None
  try:
   order_id=int(reference)
   row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='order'",(order_id,)).fetchone()
  except (TypeError,ValueError):
   row=None
  if row is None:
   rows=conn.execute("SELECT * FROM workspace_records WHERE kind='order' ORDER BY id DESC LIMIT 250").fetchall()
   for candidate in rows:
    data=json.loads(candidate["data_json"])
    if data.get("supplier_order_reference")==str(reference):
     row=candidate
     break
 if row is None:
  return {"matched":False,"reference":str(reference)[:150]}
 data=json.loads(row["data_json"])
 return {"matched":True,"order_id":row["id"],"product_title":data.get("product_title"),
         "order_status":row["status"],"fulfillment_status":data.get("fulfillment_status"),
         "tracking":data.get("tracking"),"supplier_order_status":data.get("supplier_order_status")}


def open_ticket(db_path,subject,message,order_reference=None,customer_reference=None,channel="manual"):
 if channel not in {"manual","email_import","store_import","marketplace_import"}:raise ValueError("unsupported channel")
 if not isinstance(message,str) or not message.strip() or len(message)>5000:raise ValueError("message must be 1-5000 characters")
 if customer_reference is not None and (not isinstance(customer_reference,(str,int)) or isinstance(customer_reference,bool) or len(str(customer_reference))>150):raise ValueError("customer_reference must be at most 150 characters")
 context=_find_order_context(db_path,order_reference)
 status=context.get("fulfillment_status") or context.get("order_status") if context and context.get("matched") else None
 result=triage_support_ticket(subject,message,status)
 data={**result,"message":message,"order_reference":str(order_reference)[:150] if order_reference else None,
 "order_context":context,"customer_reference":str(customer_reference)[:150] if customer_reference else None,"channel":channel,
 "response_status":"draft_only","history":[]}
 return create_record(db_path,"support_ticket",result["subject"],data,"escalated" if result["priority"]=="urgent" else "open")
def draft_response(db_path,ticket_id,response):
 if not isinstance(response,str) or not response.strip() or len(response)>3000:raise ValueError("response must be 1-3000 characters")
 with connect(db_path) as conn:
  conn.execute("BEGIN IMMEDIATE");row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='support_ticket'",(ticket_id,)).fetchone()
  if row is None:raise ValueError("ticket not found")
  data=json.loads(row["data_json"]);data["draft_reply"]=response.strip();data["response_status"]="draft_only"
  data.setdefault("history",[]).append({"type":"response_drafted","response":response.strip(),"sent":False})
  conn.execute("UPDATE workspace_records SET data_json=?,status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(json_dump(data),"escalated" if data.get("priority")=="urgent" else "drafted",ticket_id))
  conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",("support.response.drafted","support_ticket",str(ticket_id),"{}"))
 return {"id":ticket_id,"response":response.strip(),"sent":False,"requires_human_review":True}
def add_internal_note(db_path,ticket_id,note,author="operator"):
 if not isinstance(note,str) or not note.strip() or len(note)>2000:raise ValueError("note must be 1-2000 characters")
 with connect(db_path) as conn:
  conn.execute("BEGIN IMMEDIATE");row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='support_ticket'",(ticket_id,)).fetchone()
  if row is None:raise ValueError("ticket not found")
  data=json.loads(row["data_json"]);data.setdefault("history",[]).append({"type":"note","note":note.strip(),"author":str(author)[:80]})
  conn.execute("UPDATE workspace_records SET data_json=? WHERE id=?",(json_dump(data),ticket_id))
 return {"id":ticket_id,"history":data["history"]}
def support_queue(db_path):
 rows=list_records(db_path,"support_ticket",250)
 return {"tickets":[r for r in rows if r["status"]!="resolved"],"urgent_count":sum(r["data"].get("priority")=="urgent" for r in rows),"automatic_sends":0}


def draft_contextual_response(db_path, ticket_id):
 with connect(db_path) as conn:
  row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='support_ticket'",(ticket_id,)).fetchone()
 if row is None:
  raise ValueError("ticket not found")
 data=json.loads(row["data_json"])
 context=data.get("order_context")
 if not context or not context.get("matched"):
  reply="Thanks for contacting us. We are checking the order details and will follow up with verified information."
 elif context.get("fulfillment_status")=="delivered":
  reply="Our recorded order status shows this order as delivered. If you have not received it, please reply so the delivery issue can be investigated."
 elif context.get("fulfillment_status")=="shipped":
  tracking=context.get("tracking")
  reply="Our recorded order status shows this order has shipped." + ((" The recorded tracking reference is "+tracking+".") if tracking else "") + " Please let us know if you need help checking the delivery."
 elif context.get("fulfillment_status")=="in_production":
  reply="Our recorded order status shows this order is in production. We will share a further update when verified dispatch information is available."
 elif context.get("fulfillment_status")=="delayed":
  reply="Our records flag this order as delayed. We are checking the latest fulfilment details and will update you when confirmed."
 elif context.get("fulfillment_status")=="cancelled" or context.get("order_status")=="cancelled":
  reply="Our records show this order was cancelled. If you need help with the next steps, please let us know."
 else:
  reply="Thanks for reaching out. We are checking the recorded order status and will follow up with verified information."
 return draft_response(db_path,ticket_id,reply)
