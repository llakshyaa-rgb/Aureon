"""Local commerce workflow services with validated state transitions."""
import json,math,re
from .db import connect,json_dump
SCHEMA="""CREATE TABLE IF NOT EXISTS workspace_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,status TEXT NOT NULL,title TEXT NOT NULL,
 data_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE INDEX IF NOT EXISTS idx_workspace_kind_created ON workspace_records(kind,id DESC);
CREATE TABLE IF NOT EXISTS approvals (
 id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT NOT NULL,target_type TEXT NOT NULL,target_id TEXT NOT NULL,
 amount REAL,currency TEXT,status TEXT NOT NULL DEFAULT 'pending',reason TEXT NOT NULL DEFAULT '',
 expires_at TEXT,created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),decided_at TEXT);
CREATE TABLE IF NOT EXISTS finance_entries (
 id INTEGER PRIMARY KEY AUTOINCREMENT,entry_type TEXT NOT NULL,amount REAL NOT NULL,currency TEXT NOT NULL,
 description TEXT NOT NULL,reference TEXT,actual INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));"""
KINDS={"opportunity","product","design","listing","order","support_ticket","campaign","supplier","customer"}
STATUSES={"opportunity":{"research","investigate","shortlisted","rejected"},"product":{"draft","research","approved","archived"},
"design":{"brief","generated","review","approved","rejected"},"listing":{"draft","review","approved","published"},
"order":{"simulated","awaiting_approval","approved","fulfilled","cancelled"},"support_ticket":{"open","drafted","escalated","resolved"},
"campaign":{"draft","review","approved","running","paused","completed"},"supplier":{"research","verified","rejected"},"customer":{"active","restricted"}}
TRANSITIONS={
"opportunity":{"research":{"investigate","shortlisted","rejected"},"investigate":{"shortlisted","rejected","research"},"shortlisted":{"rejected"},"rejected":set()},
"product":{"draft":{"research","approved","archived"},"research":{"draft","approved","archived"},"approved":{"archived"},"archived":set()},
"design":{"brief":{"generated","review","rejected"},"generated":{"review","approved","rejected"},"review":{"generated","approved","rejected"},"approved":set(),"rejected":{"brief"}},
"listing":{"draft":{"review"},"review":{"draft","approved"},"approved":{"published"},"published":set()},
"order":{"simulated":{"awaiting_approval","cancelled"},"awaiting_approval":{"simulated","approved","cancelled"},"approved":{"fulfilled","cancelled"},"fulfilled":set(),"cancelled":set()},
"support_ticket":{"open":{"drafted","escalated","resolved"},"drafted":{"open","escalated","resolved"},"escalated":{"resolved"},"resolved":set()},
"campaign":{"draft":{"review"},"review":{"draft","approved"},"approved":{"running","paused"},"running":{"paused","completed"},"paused":{"running","completed"},"completed":set()},
"supplier":{"research":{"verified","rejected"},"verified":{"research","rejected"},"rejected":{"research"}},
"customer":{"active":{"restricted"},"restricted":{"active"}}}
def initialize_workspace(path):
 with connect(path) as conn: conn.executescript(SCHEMA)
def _record(row):
 item=dict(row);item["data"]=json.loads(item.pop("data_json"));return item
def create_record(path,kind,title,data=None,status=None):
 if kind not in KINDS: raise ValueError("unsupported record type")
 if not isinstance(title,str) or not title.strip() or len(title)>200: raise ValueError("title must be 1-200 characters")
 if data is not None and not isinstance(data,dict): raise ValueError("data must be an object")
 status=status or ("research" if kind in {"opportunity","supplier"} else "simulated" if kind=="order" else "open" if kind=="support_ticket" else "active" if kind=="customer" else "draft" if kind in {"product","listing","campaign"} else "brief")
 if status not in STATUSES[kind]: raise ValueError("invalid status for "+kind)
 payload=data or {}
 if kind=="opportunity":
  evidence=payload.get("evidence",[])
  if not isinstance(evidence,list) or not evidence: raise ValueError("opportunity requires evidence")
  for source in evidence:
   if not isinstance(source,dict) or not source.get("source_url") or not source.get("collected_at"): raise ValueError("each evidence item needs source_url and collected_at")
 if kind=="product":
  price=payload.get("selling_price")
  if price is not None and (isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<0): raise ValueError("selling_price must be finite and non-negative")
 with connect(path) as conn:
  cur=conn.execute("INSERT INTO workspace_records(kind,status,title,data_json) VALUES(?,?,?,?)",(kind,status,title.strip(),json_dump(payload)))
  row=conn.execute("SELECT * FROM workspace_records WHERE id=?",(cur.lastrowid,)).fetchone()
  conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",("workspace."+kind+".created",kind,str(cur.lastrowid),json_dump({"status":status})))
  return _record(row)
def list_records(path,kind=None,limit=100):
 limit=max(1,min(int(limit),250))
 with connect(path) as conn:
  rows=conn.execute("SELECT * FROM workspace_records WHERE kind=? ORDER BY id DESC LIMIT ?",(kind,limit)).fetchall() if kind else conn.execute("SELECT * FROM workspace_records ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
  return [_record(r) for r in rows]
def transition_record(path,record_id,status):
 with connect(path) as conn:
  conn.execute("BEGIN IMMEDIATE");row=conn.execute("SELECT * FROM workspace_records WHERE id=?",(record_id,)).fetchone()
  if row is None: raise ValueError("record not found")
  if status not in TRANSITIONS.get(row["kind"],{}).get(row["status"],set()): raise ValueError("invalid status transition from "+row["status"]+" to "+str(status))
  conn.execute("UPDATE workspace_records SET status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(status,record_id))
  conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",("workspace."+row["kind"]+".status",row["kind"],str(record_id),json_dump({"from":row["status"],"status":status})))
  return _record(conn.execute("SELECT * FROM workspace_records WHERE id=?",(record_id,)).fetchone())
def request_approval(path,action,target_type,target_id,reason,amount=None,currency=None):
 if action not in {"publish_listing","publish_campaign","place_supplier_order","spend_on_ads","issue_refund","send_commitment","create_shopify_draft","create_printify_draft"}: raise ValueError("unsupported approval action")
 if not isinstance(target_type,str) or not target_type.strip() or not isinstance(target_id,(str,int)) or not str(target_id).strip() or not isinstance(reason,str) or not reason.strip(): raise ValueError("target_type, target_id and reason are required")
 if amount is not None and (isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount<0): raise ValueError("amount must be finite and non-negative")
 if amount is not None and (not isinstance(currency,str) or not re.fullmatch(r"[A-Za-z]{3}",currency)): raise ValueError("currency is required for amount")
 with connect(path) as conn:
  cur=conn.execute("INSERT INTO approvals(action,target_type,target_id,amount,currency,reason) VALUES(?,?,?,?,?,?)",(action,target_type.strip(),str(target_id),amount,currency.upper() if currency else None,reason.strip()[:1000]))
  return dict(conn.execute("SELECT * FROM approvals WHERE id=?",(cur.lastrowid,)).fetchone())
def decide_approval(path,approval_id,decision):
 if decision not in {"approved","rejected"}: raise ValueError("decision must be approved or rejected")
 with connect(path) as conn:
  conn.execute("BEGIN IMMEDIATE")
  cur=conn.execute("UPDATE approvals SET status=?,decided_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='pending'",(decision,approval_id))
  if cur.rowcount!=1: raise ValueError("approval not found or already decided")
  return dict(conn.execute("SELECT * FROM approvals WHERE id=?",(approval_id,)).fetchone())
def list_approvals(path):
 with connect(path) as conn:return [dict(r) for r in conn.execute("SELECT * FROM approvals ORDER BY id DESC LIMIT 100").fetchall()]
def add_finance_entry(path,entry_type,amount,currency,description,reference=None,actual=False):
 allowed={"revenue","supplier_cost","shipping","platform_fee","payment_fee","advertising","refund","tax","other_cost"}
 if entry_type not in allowed: raise ValueError("unsupported finance entry type")
 if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount<0: raise ValueError("amount must be finite and non-negative")
 if not isinstance(currency,str) or not re.fullmatch(r"[A-Za-z]{3}",currency): raise ValueError("currency must be three-letter code")
 if not isinstance(description,str) or not description.strip(): raise ValueError("description is required")
 if not isinstance(actual,bool): raise ValueError("actual must be true or false")
 if reference is not None and not isinstance(reference,str): raise ValueError("reference must be text")
 with connect(path) as conn:
  cur=conn.execute("INSERT INTO finance_entries(entry_type,amount,currency,description,reference,actual) VALUES(?,?,?,?,?,?)",(entry_type,round(float(amount),2),currency.upper(),description.strip()[:500],reference[:150] if reference else None,int(actual)))
  return dict(conn.execute("SELECT * FROM finance_entries WHERE id=?",(cur.lastrowid,)).fetchone())
def finance_summary(path):
 with connect(path) as conn:rows=conn.execute("SELECT currency,entry_type,actual,SUM(amount) total FROM finance_entries GROUP BY currency,entry_type,actual ORDER BY currency,entry_type,actual").fetchall()
 result={}
 for r in rows:
  item=result.setdefault(r["currency"],{"actual_revenue":0.0,"actual_costs":0.0,"estimated_revenue":0.0,"estimated_costs":0.0,"breakdown":[]})
  key=("actual_" if r["actual"] else "estimated_")+("revenue" if r["entry_type"]=="revenue" else "costs")
  item[key]+=float(r["total"]);item["breakdown"].append({"type":r["entry_type"],"actual":bool(r["actual"]),"amount":round(float(r["total"]),2)})
 for item in result.values():
  for k in ("actual_revenue","actual_costs","estimated_revenue","estimated_costs"):item[k]=round(item[k],2)
  item["actual_net"]=round(item["actual_revenue"]-item["actual_costs"],2);item["estimated_net"]=round(item["estimated_revenue"]-item["estimated_costs"],2)
 return result
