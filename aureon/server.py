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
from .research import save_opportunity
from .suppliers import add_supplier,add_quote,compare_supplier_quotes,prepare_order_from_best_quote
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
from .creative import generate_vector_artwork,generate_mockup_preview,validate_svg_artwork,list_assets
from .intelligence.economics import Offer
from .intelligence.scenarios import pricing_scenarios,break_even_orders
from .intelligence.product_research import analyze_competition
from .finance_reports import profit_and_loss

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

PAGE="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aureon</title>
<style>:root{color-scheme:dark;font-family:system-ui;background:#0b1020;color:#e8edf7}body{max-width:1000px;margin:28px auto;padding:0 16px}
header,.grid{display:flex;gap:12px;justify-content:space-between;flex-wrap:wrap}h1{letter-spacing:-1px}.muted,small{color:#9aa8bd}
.panel,.stat{background:#121b30;border:1px solid #263650;border-radius:14px;padding:16px;margin:12px 0}.stat{flex:1;min-width:100px}.stat b{display:block;font-size:24px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#bcd0ee}</style>
<header><div><h1>Aureon</h1><span class="muted">Commerce operations · local control plane</span></div><small>v__VERSION__ · LOCAL WORKSPACE + LIVE PUBLIC DATA</small></header>
<section class="panel"><h2>Live opportunity discovery</h2><p class="muted">Current public Google Trends searches. Attention signals only; not validated demand or sales.</p><div class="grid"><input id="geo" value="IN" maxlength="2"><button onclick="loadTrends()">Fetch live trends</button><button onclick="collectTrends()">Save snapshot &amp; opportunities</button><button onclick="trendHistory()">View rank history</button></div><pre id="trends">Not fetched yet.</pre></section>
<section class="panel"><h2>Shopify connection</h2><p class="muted">Read your connected catalog and create unpublished drafts only.</p><button onclick="shopConnect()">Test connection</button> <button onclick="shopProducts()">Load products</button><pre id="shopStatus">Not checked.</pre><pre id="shopCatalog">No catalog loaded.</pre><h3>New unpublished draft</h3><input id="shopTitle" placeholder="Product title"><input id="shopPrice" type="number" min="0.01" step="0.01" placeholder="Price"><input id="shopDescription" placeholder="Description"><input id="shopVendor" placeholder="Vendor"><input id="shopType" placeholder="Product type"><input id="shopTags" placeholder="Tags separated by commas"><button onclick="shopDraft()">Request approval</button> <button onclick="shopCreateApprovedDraft()">Approve &amp; create draft</button><pre id="shopDraftResult"></pre></section>
<section class="panel"><h2>Printify catalog</h2><p class="muted">Live shops, print-on-demand blanks, providers and variants. Product creation is approval-gated and stays hidden from sales channels; orders and publishing are not enabled.</p><button onclick="printifyShops()">Load Printify shops</button> <button onclick="printifyBlueprints()">Load catalog</button><pre id="printifyShops">Not loaded.</pre><pre id="printifyBlueprints">Not loaded.</pre><h3>Inspect a blueprint</h3><input id="printifyBlueprintId" type="number" min="1" placeholder="Blueprint ID"><input id="printifyProviderId" type="number" min="1" placeholder="Print provider ID"><button onclick="printifyProviders()">Load providers</button> <button onclick="printifyVariants()">Load variants</button> <button onclick="printifyShipping()">Load shipping</button><pre id="printifyDetails">Select a blueprint and provider.</pre><h3>Upload design artwork</h3><input id="printifyFileName" placeholder="Artwork filename, e.g. design.png"><input id="printifyImageUrl" placeholder="Public HTTPS image URL"><button onclick="printifyUpload()">Upload artwork to Printify</button><pre id="printifyUploadResult"></pre><h3>Create an unpublished Printify product</h3><input id="printifyShopId" type="number" min="1" placeholder="Printify shop ID"><textarea id="printifyProductJson" rows="8" placeholder="Paste product JSON: title, blueprint_id, print_provider_id, variants, print_areas..."></textarea><button onclick="printifyRequestApproval()">Request approval</button> <button onclick="printifyApproveCreate()">Approve &amp; create product</button><pre id="printifyProductResult"></pre></section>
<section class="panel"><h2>Creative studio · local vector generator</h2><p class="muted">Creates editable SVG artwork locally, with print-size checks and an illustrative mockup. Not an AI image model or supplier photo.</p><div class="grid"><input id="artTitle" placeholder="Artwork title"><input id="artConcept" placeholder="Concept / supporting line"><select id="artStyle"><option>orbit</option><option>badge</option><option>type</option><option>botanical</option><option>geometric</option></select><select id="artPalette"><option>midnight</option><option>sunset</option><option>forest</option><option>mono</option><option>ocean</option></select><button onclick="generateArt()">Generate SVG artwork</button><button onclick="loadAssets()">Saved assets</button></div><pre id="creativeResult">No artwork generated.</pre><div id="creativePreview"></div></section>
<section class="panel"><h2>Create product</h2><div class="grid"><input id="productTitle" placeholder="Product name"><input id="productPrice" type="number" min="0" step="0.01" placeholder="Selling price"><input id="productCurrency" value="INR" maxlength="3"><button onclick="createProduct()">Save product</button></div><pre id="productResult"></pre></section>
<section class="panel"><h2>Record finance transaction</h2><div class="grid"><select id="financeType"><option value="revenue">Revenue</option><option value="supplier_cost">Supplier cost</option><option value="shipping">Shipping</option><option value="advertising">Advertising</option><option value="other_cost">Other cost</option></select><input id="financeAmount" type="number" min="0" step="0.01" placeholder="Amount"><input id="financeCurrency" value="INR" maxlength="3"><input id="financeDescription" placeholder="Description"><button onclick="addFinance()">Save transaction</button></div><pre id="financeResult"></pre></section>
<section class="panel"><h2>Workspace overview</h2><div class="grid" id="stats">Loading…</div></section>
<section class="panel"><h2>Finance snapshot</h2><pre id="finance">Loading…</pre></section>
<section class="panel"><h2>Recent work</h2><pre id="records">Loading…</pre></section><section class="panel"><h2>Job queue</h2><pre id="jobs">Loading…</pre></section><section class="panel"><h2>Support queue</h2><pre id="support">Loading…</pre></section><section class="panel"><h2>Campaigns</h2><pre id="campaigns">Loading…</pre></section><section class="panel"><h2>Approvals</h2><pre id="approvals">Loading…</pre></section><section class="panel"><h2>Agent runtime</h2><pre id="agents">Loading…</pre></section>
<script>async function get(p){const r=await fetch(p);if(!r.ok)throw Error((await r.text())||r.status);return r.json()}
async function post(p,b){const r=await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});const d=await r.json();if(!r.ok)throw Error(d.error||r.status);return d}
async function printifyShops(){const e=document.getElementById('printifyShops');e.textContent='Loading…';try{e.textContent=JSON.stringify((await get('/api/printify/shops')).shops,null,2)}catch(x){e.textContent=String(x)}}
async function printifyBlueprints(){const e=document.getElementById('printifyBlueprints');e.textContent='Loading…';try{e.textContent=JSON.stringify((await get('/api/printify/blueprints')).blueprints,null,2)}catch(x){e.textContent=String(x)}}
async function printifyUpload(){const e=document.getElementById('printifyUploadResult');e.textContent='Uploading…';try{const d=await post('/api/printify/uploads',{file_name:document.getElementById('printifyFileName').value,image_url:document.getElementById('printifyImageUrl').value});e.textContent=JSON.stringify(d.upload,null,2)}catch(x){e.textContent=String(x)}}
let printifyProductApprovalId=null;
function printifyProductPayload(){return {shop_id:Number(document.getElementById('printifyShopId').value),product:JSON.parse(document.getElementById('printifyProductJson').value)}}
async function printifyRequestApproval(){const e=document.getElementById('printifyProductResult');try{const a=await post('/api/printify/products/approval',printifyProductPayload());printifyProductApprovalId=a.approval.id;e.textContent='Approval #'+printifyProductApprovalId+' requested. Review the payload, then approve and create.'}catch(x){e.textContent=String(x)}}
async function printifyApproveCreate(){const e=document.getElementById('printifyProductResult');if(!printifyProductApprovalId){e.textContent='Request approval first.';return}if(!confirm('Approve creation of this unpublished Printify product?'))return;try{await post('/api/approvals/'+printifyProductApprovalId+'/decision',{decision:'approved'});const p=printifyProductPayload();const d=await post('/api/printify/products',{...p,approval_id:printifyProductApprovalId});e.textContent=JSON.stringify(d.product,null,2);printifyProductApprovalId=null}catch(x){e.textContent=String(x)}}
async function printifyProviders(){const e=document.getElementById('printifyDetails');e.textContent='Loading providers…';try{const id=document.getElementById('printifyBlueprintId').value;e.textContent=JSON.stringify((await get('/api/printify/blueprints/'+encodeURIComponent(id)+'/providers')).providers,null,2)}catch(x){e.textContent=String(x)}}
async function printifyVariants(){const e=document.getElementById('printifyDetails');e.textContent='Loading variants…';try{const b=document.getElementById('printifyBlueprintId').value,p=document.getElementById('printifyProviderId').value;e.textContent=JSON.stringify((await get('/api/printify/blueprints/'+encodeURIComponent(b)+'/providers/'+encodeURIComponent(p)+'/variants')).variants,null,2)}catch(x){e.textContent=String(x)}}
async function printifyShipping(){const e=document.getElementById('printifyDetails');e.textContent='Loading shipping…';try{const b=document.getElementById('printifyBlueprintId').value,p=document.getElementById('printifyProviderId').value;e.textContent=JSON.stringify((await get('/api/printify/blueprints/'+encodeURIComponent(b)+'/providers/'+encodeURIComponent(p)+'/shipping')).shipping,null,2)}catch(x){e.textContent=String(x)}}
async function shopConnect(){const e=document.getElementById('shopStatus');e.textContent='Checking…';try{e.textContent=JSON.stringify(await get('/api/shopify/connection'),null,2)}catch(x){e.textContent=String(x)}}
async function shopProducts(){const e=document.getElementById('shopCatalog');e.textContent='Loading…';try{const d=await get('/api/shopify/products');e.textContent=JSON.stringify(d.products,null,2)}catch(x){e.textContent=String(x)}}
let shopDraftApprovalId=null;function shopDraftPayload(){return {title:document.getElementById('shopTitle').value,price:Number(document.getElementById('shopPrice').value),description:document.getElementById('shopDescription').value,vendor:document.getElementById('shopVendor').value,product_type:document.getElementById('shopType').value,tags:document.getElementById('shopTags').value.split(',').map(x=>x.trim()).filter(Boolean)}}async function shopDraft(){const e=document.getElementById('shopDraftResult');e.textContent='Requesting approval…';try{const a=await post('/api/shopify/drafts/approval',shopDraftPayload());shopDraftApprovalId=a.approval.id;e.textContent='Approval #'+shopDraftApprovalId+' requested. Review the details, then use Approve & create draft.'}catch(x){e.textContent=String(x)}}async function shopCreateApprovedDraft(){const e=document.getElementById('shopDraftResult');if(!shopDraftApprovalId){e.textContent='Request approval first.';return}if(!confirm('Approve and create this unpublished Shopify draft?'))return;try{await post('/api/approvals/'+shopDraftApprovalId+'/decision',{decision:'approved'});const d=await post('/api/shopify/drafts',{...shopDraftPayload(),approval_id:shopDraftApprovalId});e.textContent=JSON.stringify(d.product,null,2);shopDraftApprovalId=null}catch(x){e.textContent=String(x)}}
async function collectTrends(){const el=document.getElementById('trends');el.textContent='Queueing live trend collection…';try{const d=await post('/api/trends/collect',{geo:document.getElementById('geo').value,limit:25});el.textContent='Queued local research job #'+d.job.id+'; the background worker will fetch and save unique signals.'}catch(e){el.textContent=String(e)}}
async function trendHistory(){const el=document.getElementById('trends');try{el.textContent=JSON.stringify(await get('/api/trends/history?geo='+encodeURIComponent(document.getElementById('geo').value)),null,2)}catch(e){el.textContent=String(e)}}async function loadTrends(){const el=document.getElementById('trends');el.textContent='Fetching…';try{const d=await get('/api/trends?geo='+encodeURIComponent(document.getElementById('geo').value));el.textContent=JSON.stringify(d,null,2)}catch(e){el.textContent=String(e)}}
async function generateArt(){const e=document.getElementById('creativeResult');e.textContent='Generating…';document.getElementById('creativePreview').innerHTML='';try{const d=await post('/api/creative/generate',{title:document.getElementById('artTitle').value,concept:document.getElementById('artConcept').value,style:document.getElementById('artStyle').value,palette:document.getElementById('artPalette').value});e.textContent=JSON.stringify({record_id:d.record.id,qa:d.artwork.qa,format:d.artwork.format,provenance:d.artwork.provenance},null,2);document.getElementById('creativePreview').innerHTML='<a download="aureon-artwork.svg" href="data:image/svg+xml;charset=utf-8,'+encodeURIComponent(d.artwork.svg)+'">Download editable SVG</a><div><img alt="Generated artwork preview" style="width:100%;max-width:320px;margin-top:12px;background:#e8e1d7;border-radius:12px" src="data:image/svg+xml;charset=utf-8,'+encodeURIComponent(d.artwork.svg)+'"></div>';document.getElementById('creativePreview').style.padding='12px'}catch(x){e.textContent=String(x)}}async function loadAssets(){const e=document.getElementById('creativeResult');try{const d=await get('/api/creative/assets');e.textContent=JSON.stringify(d.assets.map(x=>({id:x.id,title:x.title,status:x.status,qa:x.data.qa})),null,2)}catch(x){e.textContent=String(x)}}async function createProduct(){try{const d=await post('/api/records',{kind:'product',title:document.getElementById('productTitle').value,data:{selling_price:Number(document.getElementById('productPrice').value),currency:document.getElementById('productCurrency').value.toUpperCase()}});document.getElementById('productResult').textContent='Saved product #'+d.record.id;refresh()}catch(e){document.getElementById('productResult').textContent=String(e)}}
async function addFinance(){try{const d=await post('/api/finance',{entry_type:document.getElementById('financeType').value,amount:Number(document.getElementById('financeAmount').value),currency:document.getElementById('financeCurrency').value.toUpperCase(),description:document.getElementById('financeDescription').value,actual:true});document.getElementById('financeResult').textContent='Saved transaction #'+d.entry.id;refresh()}catch(e){document.getElementById('financeResult').textContent=String(e)}}

async function refresh(){try{const [o,f,r,j,s,m,a,g]=await Promise.all([get('/api/overview'),get('/api/finance'),get('/api/records'),get('/api/jobs'),get('/api/support'),get('/api/marketing/campaigns'),get('/api/approvals'),get('/api/agents')]);
document.getElementById('stats').innerHTML=Object.entries(o.records).map(([k,v])=>'<div class="stat"><b>'+v+'</b><small>'+k.replaceAll('_',' ')+'</small></div>').join('');
document.getElementById('finance').textContent=JSON.stringify(f.summary,null,2);
document.getElementById('records').textContent=r.records.slice(0,15).map(x=>'#'+x.id+' · '+x.kind+' · '+x.status+' · '+x.title).join('\\n')||'No records yet.';
document.getElementById('jobs').textContent=j.jobs.slice(0,10).map(x=>'#'+x.id+' · '+x.kind+' · '+x.status).join('\\n')||'No jobs yet.';
document.getElementById('support').textContent=s.tickets.slice(0,12).map(x=>'#'+x.id+' · '+x.status+' · '+x.data.priority+' · '+x.title).join('\\n')||'No open tickets.';
document.getElementById('campaigns').textContent=m.campaigns.slice(0,12).map(x=>'#'+x.id+' · '+x.status+' · '+x.channel+' · '+x.name).join('\\n')||'No campaigns.';
document.getElementById('approvals').textContent=a.approvals.filter(x=>x.status==='pending').map(x=>'#'+x.id+' · '+x.action+' · '+x.target_type+' '+x.target_id).join('\\n')||'No pending approvals.';
document.getElementById('agents').textContent=JSON.stringify(g,null,2);
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
   if path=="/health": return self._send(200,{"ok":True,"version":__version__,"mode":"local","live_data":["google_trends_public_rss"]})
   if path=="/api/trends":
    q=parse_qs(urlparse(self.path).query)
    try: return self._send(200,fetch_trending_searches(q.get("geo",["IN"])[0]))
   if path=="/api/trends/history":
    q=parse_qs(urlparse(self.path).query)
    try: return self._send(200,trend_history(db_path,q.get("geo",["IN"])[0]))
    except ValueError as exc: return self._send(400,{"error":str(exc)})
    except (ValueError,RuntimeError) as exc: return self._send(502,{"error":str(exc)})
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
   if path=="/api/finance/profit-and-loss":
    q=parse_qs(urlparse(self.path).query)
    return self._send(200,profit_and_loss(db_path,q.get("start",[None])[0],q.get("end",[None])[0],q.get("currency",[None])[0]))
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
    if path=="/api/creative/mockup":
     return self._send(200,{"mockup":generate_mockup_preview(b.get("artwork",{}))})
    if path=="/api/creative/generate":
     artwork=generate_vector_artwork(b.get("title"),b.get("concept"),b.get("style","orbit"),b.get("palette","midnight"),b.get("accent"))
     from .workflows import create_record
     record=create_record(db_path,"design",artwork["title"],{k:v for k,v in artwork.items() if k!="svg"}|{"svg":artwork["svg"],"asset_type":"vector_artwork"},"generated")
     return self._send(201,{"record":record,"artwork":artwork})
    if path=="/api/research/competitors":
     return self._send(200,analyze_competition(b.get("observations")))
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
 stop_event=threading.Event()
 worker=threading.Thread(target=background_loop,args=(db_path,stop_event),name="aureon-worker",daemon=True)
 worker.start()
 print("Aureon: http://%s:%s (local workspace + background worker; Ctrl+C to stop)"%(host,port))
 try: server.serve_forever()
 finally:
  stop_event.set();worker.join(timeout=5);server.server_close()
