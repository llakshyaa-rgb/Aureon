"""Allowlisted supervised agent task plans; no shell execution or external side effects."""
import uuid,json
from .db import connect,json_dump
from .jobs import enqueue
ALLOWED={"design.brief":{"niche","audience","product_type","style","concept"},"listing.draft":{"product","audience","keywords"},"support.triage":{"subject","message"},"marketing.draft":{"product_title","audience","channel","benefit","call_to_action"},"economics.calculate":{"channel","selling_price","product_cost"},"opportunity.assess":{"title","evidence","signals"},"campaign.metrics":{"metrics"}}
def plan_run(name,tasks):
 if not isinstance(name,str) or not name.strip() or len(name)>120:raise ValueError("plan name required")
 if not isinstance(tasks,list) or not 1<=len(tasks)<=20:raise ValueError("plan must contain 1..20 tasks")
 clean=[]
 for i,t in enumerate(tasks):
  if not isinstance(t,dict) or t.get("kind") not in ALLOWED or not isinstance(t.get("payload"),dict):raise ValueError("unsupported task or payload")
  missing=ALLOWED[t["kind"]]-set(t["payload"])
  if missing:raise ValueError("task "+str(i)+" missing "+", ".join(sorted(missing)))
  deps=t.get("depends_on",[])
  if not isinstance(deps,list) or deps:raise ValueError("dependency-gated plans are not enabled yet; submit independent tasks")
  clean.append({"step":i,"kind":t["kind"],"payload":t["payload"],"depends_on":[]})
 return {"name":name.strip(),"tasks":clean,"mode":"supervised_mock","requires_operator_review":True}
def submit_plan(db_path,name,tasks,idempotency_key=None):
 plan=plan_run(name,tasks)
 if idempotency_key is not None and (not isinstance(idempotency_key,str) or not idempotency_key.strip() or len(idempotency_key)>180):raise ValueError("idempotency_key must be 1-180 characters")
 key=idempotency_key or "plan-"+uuid.uuid4().hex
 with connect(db_path) as conn:
  rows=conn.execute("SELECT id,data_json FROM workspace_records WHERE kind='agent_run'").fetchall()
  for row in rows:
   if json.loads(row["data_json"]).get("idempotency_key")==key:return {"run_id":row["id"],"duplicate":True}
 ids=[]
 for task in plan["tasks"]:ids.append(enqueue(db_path,task["kind"],task["payload"],key+"-"+str(task["step"]))["id"])
 with connect(db_path) as conn:
  cur=conn.execute("INSERT INTO workspace_records(kind,status,title,data_json) VALUES('agent_run','queued',?,?)",(plan["name"],json_dump({**plan,"idempotency_key":key,"job_ids":ids})))
  run_id=cur.lastrowid
  conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",("agent.run.queued","agent_run",str(run_id),json_dump({"job_ids":ids})))
 return {"run_id":run_id,"job_ids":ids,"duplicate":False,"mode":"supervised_mock"}
def runtime_status(db_path):
 with connect(db_path) as conn:
  jobs={r["status"]:r["n"] for r in conn.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status")}
  rows=conn.execute("SELECT id,status,title,created_at,data_json FROM workspace_records WHERE kind='agent_run' ORDER BY id DESC LIMIT 30").fetchall()
  runs=[]
  for row in rows:
   data=json.loads(row["data_json"]);ids=data.get("job_ids",[])
   states=[]
   if ids:
    marks=",".join("?" for _ in ids)
    states=[r["status"] for r in conn.execute("SELECT status FROM jobs WHERE id IN ("+marks+")",ids).fetchall()]
   status="succeeded" if states and all(x=="succeeded" for x in states) else "failed" if any(x=="failed" for x in states) else "running" if any(x=="running" for x in states) else "queued"
   runs.append({"id":row["id"],"status":status,"title":row["title"],"created_at":row["created_at"],"job_ids":ids,"job_statuses":states})
 return {"jobs":jobs,"recent_runs":runs,"execution":"manual worker only","shell_execution":False,"external_side_effects":False}
