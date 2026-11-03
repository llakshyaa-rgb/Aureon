"""Persistent customer-support tickets and human-reviewed response drafts."""
from .commerce import triage_support_ticket
from .workflows import create_record,list_records
from .db import connect,json_dump
import json
def open_ticket(db_path,subject,message,order_reference=None,customer_reference=None,channel="manual"):
 if channel not in {"manual","email_import","store_import","marketplace_import"}:raise ValueError("unsupported channel")
 if not isinstance(message,str) or not message.strip() or len(message)>5000:raise ValueError("message must be 1-5000 characters")
 result=triage_support_ticket(subject,message)
 data={**result,"message":message,"order_reference":str(order_reference)[:150] if order_reference else None,
 "customer_reference":str(customer_reference)[:150] if customer_reference else None,"channel":channel,
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
