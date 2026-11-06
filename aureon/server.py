"""Local-only HTTP control plane."""
import json
import hashlib
import math
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from . import __version__
from .db import connect,initialize
from .jobs import enqueue,list_jobs,recover_interrupted
from .workflows import (initialize_workspace,create_record,list_records,transition_record,
 request_approval,decide_approval,list_approvals,add_finance_entry,finance_summary)
from .product_catalog import list_products,update_product
from .research import save_opportunity
from .suppliers import add_supplier,add_quote,compare_supplier_quotes,prepare_order_from_best_quote,record_supplier_performance,supplier_scorecard
from .operations import create_order,request_supplier_order_approval,record_supplier_submission,update_tracking,request_refund_review
from .analytics import record_campaign_metrics,summarize_campaigns
from .scheduler import initialize_scheduler,schedule_job,enqueue_due,list_scheduled
from .support import open_ticket,draft_response,draft_contextual_response,add_internal_note,support_queue
from .marketing import create_campaign,request_campaign_approval,campaign_overview
from .finance import record_transaction,reconcile,cashflow_projection,financial_dashboard
from .agents import submit_plan,runtime_status
from .command_center import dashboard_snapshot,interpret_command
from .trends import fetch_trending_searches,trend_history
from .providers import shopify, printify
from .worker import background_loop
from .creative import generate_vector_artwork,generate_mockup_preview,validate_svg_artwork,list_assets,create_collection
from .intelligence.economics import Offer
from .intelligence.scenarios import pricing_scenarios,break_even_orders
from .intelligence.product_research import analyze_competition
from .finance_reports import profit_and_loss
from .intelligence.evaluation import evaluate_product_opportunity
from .experiments import create_experiment,record_variant_observation,compare_experiment
from .backups import backup_if_due,backup_database,list_backups

def _shopify_draft_payload(body):
 title=str(body.get("title") or "").strip()
 description=str(body.get("description") or "")
 vendor=str(body.get("vendor") or "")[:255]
 product_type=str(body.get("product_type") or "")[:255]
 if not title or len(title)>255: raise ValueError("title is required and must be 255 characters or fewer")
 if len(description)>5000: raise ValueError("description must be 5000 characters or fewer")
 try: price=round(float(body.get("price")),2)
 except (TypeError,ValueError): raise ValueError("price must be a positive amount") from None
 if isinstance(body.get('price'),bool) or not math.isfinite(price) or price<=0: raise ValueError("price must be a positive amount")
 raw_tags=body.get("tags",[])
 tags=[str(tag).strip()[:80] for tag in raw_tags if str(tag).strip()][:20] if isinstance(raw_tags,list) else []
 return {"title":title,"price":price,"description":description,"vendor":vendor,"product_type":product_type,"tags":tags}

def _shopify_draft_key(payload):
 store,_token=shopify.configured()
 raw=json.dumps({"store":store,"payload":payload},sort_keys=True,separators=(",",":"),ensure_ascii=False)
 return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _printify_draft_key(shop_id, product):
 raw=json.dumps({"shop_id":str(shop_id),"product":product},sort_keys=True,separators=(",",":"),ensure_ascii=False)
 return hashlib.sha256(raw.encode("utf-8")).hexdigest()

from pathlib import Path

PAGE=(Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
      .replace("__VERSION__",__version__))

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
   if path=="/health": return self._send(200,{"ok":True,"version":__version__,"mode":"local","live_data":["google_trends_public_rss"]})
   if path=="/api/trends":
    q=parse_qs(urlparse(self.path).query)
    try: return self._send(200,fetch_trending_searches(q.get("geo",["IN"])[0]))
    except ValueError as exc: return self._send(400,{"error":str(exc)})
    except RuntimeError as exc: return self._send(502,{"error":str(exc)})
   if path=="/api/trends/history":
    q=parse_qs(urlparse(self.path).query)
    try: return self._send(200,trend_history(db_path,q.get("geo",["IN"])[0]))
    except ValueError as exc: return self._send(400,{"error":str(exc)})
    except RuntimeError as exc: return self._send(502,{"error":str(exc)})
   if path=="/api/providers": return self._send(200,{"runtime":"local","live_data_sources":[{"name":"Google Trends public RSS","status":"available_without_credentials"}],"commerce_integrations":[shopify.health(),printify.health(),{"name":"Printful","mode":"not_implemented"}]})
   if path=="/api/printify/shops":
    try: return self._send(200,{"shops":printify.shops()})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"error":str(exc)})
   if path=="/api/printify/blueprints":
    try: return self._send(200,{"blueprints":printify.blueprints()})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"error":str(exc)})
   if path.startswith("/api/printify/blueprints/") and path.endswith("/providers"):
    try: return self._send(200,{"providers":printify.print_providers(path.split("/")[4])})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"error":str(exc)})
   if path.startswith("/api/printify/blueprints/") and path.endswith("/variants"):
    try:
     parts=path.split("/")
     return self._send(200,{"variants":printify.variants(parts[4],parts[6])})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"error":str(exc)})
   if path.startswith("/api/printify/blueprints/") and path.endswith("/shipping"):
    try:
     parts=path.split("/")
     return self._send(200,{"shipping":printify.shipping(parts[4],parts[6])})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"error":str(exc)})
   if path=="/api/shopify/connection":
    try: return self._send(200,{"connected":True,"shop":shopify.shop_info()})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"connected":False,"error":str(exc)})
   if path=="/api/shopify/products":
    try: return self._send(200,{"products":shopify.products()})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"error":str(exc)})
   if path=="/api/backups": return self._send(200,{"backups":list_backups(db_path)})
   if path=="/api/overview":
    with connect(db_path) as c:
     jobs=c.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status").fetchall()
     records=c.execute("SELECT kind,COUNT(*) n FROM workspace_records GROUP BY kind").fetchall()
    return self._send(200,{"jobs":{r["status"]:r["n"] for r in jobs},"records":{r["kind"]:r["n"] for r in records}})
   if path=="/api/jobs": return self._send(200,{"jobs":list_jobs(db_path)})
   if path=="/api/records": return self._send(200,{"records":list_records(db_path,parse_qs(urlparse(self.path).query).get("kind",[None])[0])})
   if path=="/api/products":
    q=parse_qs(urlparse(self.path).query)
    try: return self._send(200,{"products":list_products(db_path,q.get("q",[""])[0],q.get("status",[""])[0])})
    except ValueError as exc: return self._send(400,{"error":str(exc)})
   if path=="/api/approvals": return self._send(200,{"approvals":list_approvals(db_path)})
   if path=="/api/finance": return self._send(200,{"summary":finance_summary(db_path)})
   if path=="/api/suppliers": return self._send(200,{"suppliers":list_records(db_path,"supplier",250)})
   if path=="/api/suppliers/compare":
    q=parse_qs(urlparse(self.path).query)
    try: return self._send(200,compare_supplier_quotes(db_path,q.get("product_type",[""])[0],q.get("destination",[""])[0],q.get("currency",["USD"])[0]))
    except ValueError as exc: return self._send(400,{"error":str(exc)})
   if path.startswith("/api/suppliers/") and path.endswith("/scorecard"):
    try: return self._send(200,supplier_scorecard(db_path,int(path.split("/")[3])))
    except ValueError as exc: return self._send(400,{"error":str(exc)})
   if path=="/api/campaigns/metrics": return self._send(200,{"campaigns":summarize_campaigns(db_path)})
   if path=="/api/schedules": return self._send(200,{"schedules":list_scheduled(db_path)})
   if path=="/api/support": return self._send(200,support_queue(db_path))
   if path=="/api/marketing/campaigns": return self._send(200,{"campaigns":campaign_overview(db_path)})
   if path.startswith("/api/marketing/experiments/"):
    try: return self._send(200,compare_experiment(db_path,int(path.split("/")[4])))
    except ValueError as exc: return self._send(400,{"error":str(exc)})
   if path=="/api/finance/dashboard": return self._send(200,financial_dashboard(db_path))
   if path=="/api/finance/profit-and-loss":
    q=parse_qs(urlparse(self.path).query)
    try: return self._send(200,profit_and_loss(db_path,q.get("start",[None])[0],q.get("end",[None])[0],q.get("currency",[None])[0]))
    except ValueError as exc: return self._send(400,{"error":str(exc)})
   if path=="/api/creative/assets": return self._send(200,{"assets":list_assets(db_path)})
   if path=="/api/agents": return self._send(200,runtime_status(db_path))
   if path=="/api/command-center": return self._send(200,dashboard_snapshot(db_path))
   return self._send(404,{"error":"not_found"})
  def do_POST(self):
   path=urlparse(self.path).path
   try:
    b=self._body()
    if path=="/api/shopify/drafts/approval":
     draft=_shopify_draft_payload(b)
     approval=request_approval(db_path,"create_shopify_draft","shopify_draft",_shopify_draft_key(draft),"Approve creation of this unpublished Shopify draft")
     return self._send(201,{"approval":approval,"draft":draft})
    if path=="/api/shopify/drafts":
     draft=_shopify_draft_payload(b);approval_id=b.get("approval_id")
     if isinstance(approval_id,bool) or not isinstance(approval_id,int): raise ValueError("approval_id is required")
     with connect(db_path) as conn:
      conn.execute("BEGIN IMMEDIATE")
      approval=conn.execute("SELECT * FROM approvals WHERE id=?",(approval_id,)).fetchone()
      if approval is None or approval["status"]!="approved" or approval["action"]!="create_shopify_draft" or approval["target_type"]!="shopify_draft" or approval["target_id"]!=_shopify_draft_key(draft):
       raise ValueError("a matching approved Shopify draft request is required")
      changed=conn.execute("UPDATE approvals SET status='consumed' WHERE id=? AND status='approved'",(approval_id,))
      if changed.rowcount!=1: raise ValueError("approval has already been used")
     product=shopify.create_draft_product(draft["title"],draft["price"],draft["description"],draft["vendor"],draft["product_type"],draft["tags"])
     return self._send(201,{"product":product,"published":False,"provider":"Shopify","approval_id":approval_id})
    if path=="/api/printify/uploads":
     uploaded=printify.upload_image_url(b.get("file_name"),b.get("image_url"))
     return self._send(201,{"upload":uploaded})
    if path=="/api/printify/products/approval":
     shop_id,product=printify.validate_product(b.get("shop_id"),b.get("product"))
     approval=request_approval(db_path,"create_printify_draft","printify_product",_printify_draft_key(shop_id,product),"Approve creation of this hidden Printify product")
     return self._send(201,{"approval":approval,"shop_id":shop_id,"product":product,"visible":False})
    if path=="/api/printify/products":
     shop_id,product=printify.validate_product(b.get("shop_id"),b.get("product"));approval_id=b.get("approval_id")
     if isinstance(approval_id,bool) or not isinstance(approval_id,int): raise ValueError("approval_id is required")
     with connect(db_path) as conn:
      conn.execute("BEGIN IMMEDIATE")
      approval=conn.execute("SELECT * FROM approvals WHERE id=?",(approval_id,)).fetchone()
      if approval is None or approval["status"]!="approved" or approval["action"]!="create_printify_draft" or approval["target_type"]!="printify_product" or approval["target_id"]!=_printify_draft_key(shop_id,product):
       raise ValueError("a matching approved Printify product request is required")
      changed=conn.execute("UPDATE approvals SET status='consumed' WHERE id=? AND status='approved'",(approval_id,))
      if changed.rowcount!=1: raise ValueError("approval has already been used")
     created=printify.create_product(shop_id,product)
     return self._send(201,{"product":created,"published":False,"provider":"Printify","approval_id":approval_id})
    if path=="/api/backups":
     return self._send(201,{"backup":backup_database(db_path)})
    if path=="/api/creative/collections":
     return self._send(201,create_collection(db_path,b.get("title"),b.get("concept"),b.get("styles"),b.get("palette","midnight")))
    if path=="/api/creative/mockup":
     return self._send(200,{"mockup":generate_mockup_preview(b.get("artwork",{}))})
    if path=="/api/creative/generate":
     artwork=generate_vector_artwork(b.get("title"),b.get("concept"),b.get("style","orbit"),b.get("palette","midnight"),b.get("accent"))
     from .workflows import create_record
     record=create_record(db_path,"design",artwork["title"],{k:v for k,v in artwork.items() if k!="svg"}|{"svg":artwork["svg"],"asset_type":"vector_artwork"},"generated")
     return self._send(201,{"record":record,"artwork":artwork})
    if path=="/api/research/competitors":
     return self._send(200,analyze_competition(b.get("observations")))
    if path=="/api/opportunities/evaluate":
     return self._send(201,evaluate_product_opportunity(db_path,b.get("title"),b.get("evidence"),b.get("signals"),b.get("observations"),b.get("offer"),b.get("region","global"),b.get("business_model","undecided")))
    if path=="/api/economics/scenarios":
     offer=Offer(**b.get("offer",{}))
     return self._send(200,pricing_scenarios(offer,b.get("prices"),b.get("target_margin",0.25)))
    if path=="/api/economics/break-even":
     return self._send(200,break_even_orders(b.get("fixed_costs"),b.get("contribution_per_order")))
    if path=="/api/trends/collect":
     geo=b.get("geo","IN");limit=b.get("limit",25)
     if not isinstance(geo,str) or len(geo)!=2 or not geo.isascii() or not geo.isalpha(): raise ValueError("geo must be a two-letter country code")
     if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100: raise ValueError("limit must be between 1 and 100")
     return self._send(202,{"job":enqueue(db_path,"trends.collect",{"geo":geo.upper(),"limit":limit},b.get("idempotency_key"))})
    if path=="/api/jobs": return self._send(201,{"job":enqueue(db_path,str(b.get("kind","")),b.get("payload",{}),b.get("idempotency_key"))})
    if path=="/api/records": return self._send(201,{"record":create_record(db_path,b.get("kind"),b.get("title"),b.get("data",{}),b.get("status"))})
    if path=="/api/opportunities/assess": return self._send(201,save_opportunity(db_path,b.get("title"),b.get("evidence"),b.get("signals"),b.get("region","global"),b.get("business_model","undecided")))
    if path=="/api/suppliers": return self._send(201,{"supplier":add_supplier(db_path,b.get("name"),b.get("provider"),b.get("product_type"),b.get("website"),b.get("notes",""))})
    if path.startswith("/api/suppliers/") and path.endswith("/quotes"):
     sid=int(path.split("/")[3]);return self._send(201,{"quote":add_quote(db_path,sid,b.get("quote",{}))})
    if path.startswith("/api/suppliers/") and path.endswith("/performance"):
     sid=int(path.split("/")[3]);return self._send(201,record_supplier_performance(db_path,sid,b.get("metrics",{})))
    if path=="/api/orders/prepare-from-quote":
     return self._send(201,prepare_order_from_best_quote(db_path,b.get("product_title"),b.get("quantity"),b.get("product_type"),b.get("destination"),b.get("currency")))
    if path=="/api/orders": return self._send(201,{"order":create_order(db_path,b.get("product_title"),b.get("quantity"),b.get("unit_cost"),b.get("currency"),b.get("supplier_id"),b.get("customer_reference"))})
    if path.startswith("/api/orders/") and path.endswith("/approval"):
     oid=int(path.split("/")[3]);order,approval=request_supplier_order_approval(db_path,oid,b.get("reason","Review supplier order"));return self._send(201,{"order":order,"approval":approval})
    if path.startswith("/api/orders/") and path.endswith("/submit"):
     oid=int(path.split("/")[3]);return self._send(200,{"order":record_supplier_submission(db_path,oid,b.get("approval_id"),b.get("supplier_order_reference"))})
    if path.startswith("/api/orders/") and path.endswith("/tracking"):
     oid=int(path.split("/")[3]);return self._send(200,{"order":update_tracking(db_path,oid,b.get("tracking_code"),b.get("fulfillment_status"))})
    if path.startswith("/api/orders/") and path.endswith("/refund-review"):
     oid=int(path.split("/")[3]);return self._send(201,{"approval":request_refund_review(db_path,oid,b.get("amount"),b.get("reason","Refund review"))})
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
    if path.startswith("/api/support/") and path.endswith("/contextual-response"):
     tid=int(path.split("/")[3]);return self._send(200,draft_contextual_response(db_path,tid))
    if path.startswith("/api/support/") and path.endswith("/response"):
     tid=int(path.split("/")[3]);return self._send(200,draft_response(db_path,tid,b.get("response","")))
    if path.startswith("/api/support/") and path.endswith("/notes"):
     tid=int(path.split("/")[3]);return self._send(200,add_internal_note(db_path,tid,b.get("note",""),b.get("author","operator")))
    if path=="/api/marketing/experiments":
     return self._send(201,{"experiment":create_experiment(db_path,b.get("name"),b.get("hypothesis"),b.get("channel"),b.get("variants"))})
    if path.startswith("/api/marketing/experiments/") and path.endswith("/observations"):
     experiment_id=int(path.split("/")[4])
     return self._send(201,{"observation":record_variant_observation(db_path,experiment_id,b.get("variant_key"),b.get("metrics",{}))})
    if path=="/api/marketing/campaigns": return self._send(201,{"campaign":create_campaign(db_path,b.get("name",""),b.get("product_title",""),b.get("audience",""),b.get("channel",""),b.get("benefit",""),b.get("call_to_action",""),b.get("budget"),b.get("currency","USD"))})
    if path.startswith("/api/marketing/campaigns/") and path.endswith("/approval"):
     cid=int(path.split("/")[4]);return self._send(201,{"approval":request_campaign_approval(db_path,cid,b.get("action",""),b.get("amount"),b.get("reason","Human review required"))})
    if path=="/api/agents/plans": return self._send(201,submit_plan(db_path,b.get("name",""),b.get("tasks"),b.get("idempotency_key")))
    if path=="/api/commands/interpret": return self._send(200,interpret_command(b.get("command","")))
    return self._send(404,{"error":"not_found"})
   except RuntimeError as exc: return self._send(502,{"error":str(exc)})
   except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc: return self._send(400,{"error":str(exc)})
  def do_PATCH(self):
   path=urlparse(self.path).path
   if path.startswith("/api/products/"):
    try: return self._send(200,{"product":update_product(db_path,int(path.split("/")[3]),self._body())})
    except (ValueError,TypeError,json.JSONDecodeError) as exc: return self._send(400,{"error":str(exc)})
   if path.startswith("/api/records/"):
    try: return self._send(200,{"record":transition_record(db_path,int(path.split("/")[3]),self._body().get("status",""))})
    except (ValueError,TypeError,json.JSONDecodeError) as exc: return self._send(400,{"error":str(exc)})
   return self._send(404,{"error":"not_found"})
  def log_message(self,fmt,*args): print("[http] "+(fmt%args))
 return Handler
def serve(host,port,db_path):
 if host not in {"127.0.0.1","localhost","::1"}: raise ValueError("Aureon currently binds to localhost only")
 initialize(db_path);initialize_workspace(db_path);initialize_scheduler(db_path)
 try:
  backup=backup_if_due(db_path)
  if backup["created"]: print("Verified database backup:",backup["path"])
 except Exception as exc:
  print("[backup] automatic backup failed:",str(exc))
 recovered=recover_interrupted(db_path)
 if recovered["requeued"] or recovered["failed"]: print("Recovered interrupted jobs:",recovered)
 server=ThreadingHTTPServer((host,port),make_handler(db_path))
 stop_event=threading.Event()
 worker=threading.Thread(target=background_loop,args=(db_path,stop_event),name="aureon-worker",daemon=True)
 worker.start()
 print("Aureon: http://%s:%s (local workspace + background worker; Ctrl+C to stop)"%(host,port))
 try: server.serve_forever()
 finally:
  stop_event.set();worker.join(timeout=5);server.server_close()
