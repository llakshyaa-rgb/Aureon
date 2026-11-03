"""Local-only HTTP control plane."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from . import __version__
from .db import connect,initialize
from .jobs import enqueue,list_jobs,recover_interrupted
from .workflows import (initialize_workspace,create_record,list_records,transition_record,
 request_approval,decide_approval,list_approvals,add_finance_entry,finance_summary)
from .research import save_opportunity
from .suppliers import add_supplier,add_quote,compare_supplier_quotes
from .operations import create_order,request_supplier_order_approval,record_supplier_submission,update_tracking
from .analytics import record_campaign_metrics,summarize_campaigns
from .scheduler import initialize_scheduler,schedule_job,enqueue_due,list_scheduled
from .support import open_ticket,draft_response,add_internal_note,support_queue
from .marketing import create_campaign,request_campaign_approval,campaign_overview
from .finance import record_transaction,reconcile,cashflow_projection,financial_dashboard
from .agents import submit_plan,runtime_status
from .command_center import dashboard_snapshot,interpret_command
PAGE="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aureon</title>
<style>:root{color-scheme:dark;font-family:system-ui;background:#0b1020;color:#e8edf7}body{max-width:1000px;margin:28px auto;padding:0 16px}
header,.grid{display:flex;gap:12px;justify-content:space-between;flex-wrap:wrap}h1{letter-spacing:-1px}.muted,small{color:#9aa8bd}
.panel,.stat{background:#121b30;border:1px solid #263650;border-radius:14px;padding:16px;margin:12px 0}.stat{flex:1;min-width:100px}.stat b{display:block;font-size:24px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#bcd0ee}</style>
<header><div><h1>Aureon</h1><span class="muted">Commerce operations · local control plane</span></div><small>v__VERSION__ · MOCK MODE</small></header>
<section class="panel"><h2>Workspace overview</h2><div class="grid" id="stats">Loading…</div></section>
<section class="panel"><h2>Finance snapshot</h2><pre id="finance">Loading…</pre></section>
<section class="panel"><h2>Recent work</h2><pre id="records">Loading…</pre></section><section class="panel"><h2>Job queue</h2><pre id="jobs">Loading…</pre></section>
<script>async function get(p){const r=await fetch(p);if(!r.ok)throw Error(r.status);return r.json()}
async function refresh(){try{const [o,f,r,j]=await Promise.all([get('/api/overview'),get('/api/finance'),get('/api/records'),get('/api/jobs')]);
document.getElementById('stats').innerHTML=Object.entries(o.records).map(([k,v])=>'<div class="stat"><b>'+v+'</b><small>'+k.replaceAll('_',' ')+'</small></div>').join('');
document.getElementById('finance').textContent=JSON.stringify(f.summary,null,2);
document.getElementById('records').textContent=r.records.slice(0,15).map(x=>'#'+x.id+' · '+x.kind+' · '+x.status+' · '+x.title).join('\\n')||'No records yet.';
document.getElementById('jobs').textContent=j.jobs.slice(0,10).map(x=>'#'+x.id+' · '+x.kind+' · '+x.status).join('\\n')||'No jobs yet.';
}catch(e){document.getElementById('records').textContent='API unavailable: '+e}}refresh();setInterval(refresh,5000);</script></html>""".replace("__VERSION__",__version__)
def make_handler(db_path):
 class Handler(BaseHTTPRequestHandler):
  def _send(self,status,body,content_type="application/json"):
   data=body.encode() if isinstance(body,str) else json.dumps(body).encode()
   self.send_response(status);self.send_header("Content-Type",content_type+"; charset=utf-8");self.send_header("Content-Length",str(len(data)))
   self.send_header("X-Content-Type-Options","nosniff");self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(data)
  def _body(self):
   size=int(self.headers.get("Content-Length","0"))
   if size<1 or size>65536: raise ValueError("body_size_invalid")
   data=json.loads(self.rfile.read(size))
   if not isinstance(data,dict): raise ValueError("expected_object")
   return data
  def do_GET(self):
   path=urlparse(self.path).path
   if path=="/": return self._send(200,PAGE,"text/html")
   if path=="/health": return self._send(200,{"ok":True,"version":__version__,"mode":"mock"})
   if path=="/api/overview":
    with connect(db_path) as c:
     jobs=c.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status").fetchall()
     records=c.execute("SELECT kind,COUNT(*) n FROM workspace_records GROUP BY kind").fetchall()
    return self._send(200,{"jobs":{r["status"]:r["n"] for r in jobs},"records":{r["kind"]:r["n"] for r in records}})
   if path=="/api/jobs": return self._send(200,{"jobs":list_jobs(db_path)})
   if path=="/api/records": return self._send(200,{"records":list_records(db_path,parse_qs(urlparse(self.path).query).get("kind",[None])[0])})
   if path=="/api/approvals": return self._send(200,{"approvals":list_approvals(db_path)})
   if path=="/api/finance": return self._send(200,{"summary":finance_summary(db_path)})
   if path=="/api/suppliers/compare":
    q=parse_qs(urlparse(self.path).query);return self._send(200,compare_supplier_quotes(db_path,q.get("product_type",[""])[0],q.get("destination",[""])[0],q.get("currency",["USD"])[0]))
   if path=="/api/campaigns/metrics": return self._send(200,{"campaigns":summarize_campaigns(db_path)})
   if path=="/api/schedules": return self._send(200,{"schedules":list_scheduled(db_path)})
   if path=="/api/support": return self._send(200,support_queue(db_path))
   if path=="/api/marketing/campaigns": return self._send(200,{"campaigns":campaign_overview(db_path)})
   if path=="/api/finance/dashboard": return self._send(200,financial_dashboard(db_path))
   if path=="/api/agents": return self._send(200,runtime_status(db_path))
   if path=="/api/command-center": return self._send(200,dashboard_snapshot(db_path))
   return self._send(404,{"error":"not_found"})
  def do_POST(self):
   path=urlparse(self.path).path
   try:
    b=self._body()
    if path=="/api/jobs": return self._send(201,{"job":enqueue(db_path,str(b.get("kind","")),b.get("payload",{}),b.get("idempotency_key"))})
    if path=="/api/records": return self._send(201,{"record":create_record(db_path,b.get("kind"),b.get("title"),b.get("data",{}),b.get("status"))})
    if path=="/api/opportunities/assess": return self._send(201,save_opportunity(db_path,b.get("title"),b.get("evidence"),b.get("signals"),b.get("region","global"),b.get("business_model","undecided")))
    if path=="/api/suppliers": return self._send(201,{"supplier":add_supplier(db_path,b.get("name"),b.get("provider"),b.get("product_type"),b.get("website"),b.get("notes",""))})
    if path.startswith("/api/suppliers/") and path.endswith("/quotes"):
     sid=int(path.split("/")[3]);return self._send(201,{"quote":add_quote(db_path,sid,b.get("quote",{}))})
    if path=="/api/orders": return self._send(201,{"order":create_order(db_path,b.get("product_title"),b.get("quantity"),b.get("unit_cost"),b.get("currency"),b.get("supplier_id"),b.get("customer_reference"))})
    if path.startswith("/api/orders/") and path.endswith("/approval"):
     oid=int(path.split("/")[3]);order,approval=request_supplier_order_approval(db_path,oid,b.get("reason","Review supplier order"));return self._send(201,{"order":order,"approval":approval})
    if path.startswith("/api/orders/") and path.endswith("/submit"):
     oid=int(path.split("/")[3]);return self._send(200,{"order":record_supplier_submission(db_path,oid,b.get("approval_id"),b.get("supplier_order_reference"))})
    if path.startswith("/api/orders/") and path.endswith("/tracking"):
     oid=int(path.split("/")[3]);return self._send(200,{"order":update_tracking(db_path,oid,b.get("tracking_code"),b.get("fulfillment_status"))})
    if path.startswith("/api/campaigns/") and path.endswith("/metrics"):
     cid=int(path.split("/")[3]);return self._send(201,{"metrics":record_campaign_metrics(db_path,cid,b.get("metrics",{}))})
    if path=="/api/schedules": return self._send(201,{"schedule":schedule_job(db_path,b.get("kind"),b.get("payload",{}),b.get("run_at",""),b.get("idempotency_key",""))})
    if path=="/api/schedules/run-due": return self._send(200,{"enqueued":enqueue_due(db_path,b.get("now"),b.get("limit",50))})
    if path=="/api/approvals": return self._send(201,{"approval":request_approval(db_path,b.get("action",""),b.get("target_type",""),b.get("target_id",""),b.get("reason",""),b.get("amount"),b.get("currency"))})
    if path.startswith("/api/approvals/") and path.endswith("/decision"):
     aid=int(path.split("/")[3]);return self._send(200,{"approval":decide_approval(db_path,aid,b.get("decision",""))})
    if path=="/api/finance": return self._send(201,{"entry":record_transaction(db_path,b.get("entry_type",""),b.get("amount"),b.get("currency",""),b.get("description",""),b.get("reference"),b.get("actual",True))})
    if path=="/api/finance/reconcile": return self._send(200,reconcile(db_path,b.get("currency",""),b.get("opening_balance"),b.get("closing_balance")))
    if path=="/api/finance/forecast": return self._send(200,cashflow_projection(db_path,b.get("opening_cash"),b.get("forecast_days",30),b.get("expected_revenue",0),b.get("expected_costs",0),b.get("currency","USD")))
    if path=="/api/support": return self._send(201,{"ticket":open_ticket(db_path,b.get("subject",""),b.get("message",""),b.get("order_reference"),b.get("customer_reference"),b.get("channel","manual"))})
    if path.startswith("/api/support/") and path.endswith("/response"):
     tid=int(path.split("/")[3]);return self._send(200,draft_response(db_path,tid,b.get("response","")))
    if path.startswith("/api/support/") and path.endswith("/notes"):
     tid=int(path.split("/")[3]);return self._send(200,add_internal_note(db_path,tid,b.get("note",""),b.get("author","operator")))
    if path=="/api/marketing/campaigns": return self._send(201,{"campaign":create_campaign(db_path,b.get("name",""),b.get("product_title",""),b.get("audience",""),b.get("channel",""),b.get("benefit",""),b.get("call_to_action",""),b.get("budget"),b.get("currency","USD"))})
    if path.startswith("/api/marketing/campaigns/") and path.endswith("/approval"):
     cid=int(path.split("/")[4]);return self._send(201,{"approval":request_campaign_approval(db_path,cid,b.get("action",""),b.get("amount"),b.get("reason","Human review required"))})
    if path=="/api/agents/plans": return self._send(201,submit_plan(db_path,b.get("name",""),b.get("tasks"),b.get("idempotency_key")))
    if path=="/api/commands/interpret": return self._send(200,interpret_command(b.get("command","")))
    return self._send(404,{"error":"not_found"})
   except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc: return self._send(400,{"error":str(exc)})
  def do_PATCH(self):
   path=urlparse(self.path).path
   if path.startswith("/api/records/"):
    try: return self._send(200,{"record":transition_record(db_path,int(path.split("/")[3]),self._body().get("status",""))})
    except (ValueError,TypeError,json.JSONDecodeError) as exc: return self._send(400,{"error":str(exc)})
   return self._send(404,{"error":"not_found"})
  def log_message(self,fmt,*args): print("[http] "+(fmt%args))
 return Handler
def serve(host,port,db_path):
 if host not in {"127.0.0.1","localhost","::1"}: raise ValueError("Aureon currently binds to localhost only")
 initialize(db_path);initialize_workspace(db_path);initialize_scheduler(db_path)
 recovered=recover_interrupted(db_path)
 if recovered["requeued"] or recovered["failed"]: print("Recovered interrupted jobs:",recovered)
 server=ThreadingHTTPServer((host,port),make_handler(db_path))
 print("Aureon: http://%s:%s (mock mode; Ctrl+C to stop)"%(host,port))
 try: server.serve_forever()
 finally: server.server_close()
