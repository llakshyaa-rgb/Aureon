"""Local-only HTTP control plane."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from . import __version__
from .db import connect, initialize
from .jobs import enqueue, list_jobs, recover_interrupted
from .workflows import (initialize_workspace, create_record, list_records,
 transition_record, request_approval, decide_approval, list_approvals,
 add_finance_entry, finance_summary)

PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aureon</title><style>
:root{color-scheme:dark;font-family:system-ui;background:#0b1020;color:#e8edf7}
body{max-width:1000px;margin:28px auto;padding:0 16px}
header,.grid{display:flex;gap:12px;justify-content:space-between;flex-wrap:wrap}
h1{letter-spacing:-1px}.muted{color:#9aa8bd}
.panel,.stat{background:#121b30;border:1px solid #263650;border-radius:14px;padding:16px;margin:12px 0}
.stat{flex:1;min-width:100px}.stat b{display:block;font-size:24px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#bcd0ee}
small{color:#9aa8bd}
</style><header><div><h1>Aureon</h1><span class="muted">Commerce operations · local control plane</span></div><small>v__VERSION__ · MOCK MODE</small></header>
<section class="panel"><h2>Workspace overview</h2><div class="grid" id="stats">Loading…</div></section>
<section class="panel"><h2>Finance snapshot</h2><pre id="finance">Loading…</pre></section>
<section class="panel"><h2>Recent work</h2><pre id="records">Loading…</pre></section>
<section class="panel"><h2>Job queue</h2><pre id="jobs">Loading…</pre></section>
<script>
async function get(p){const r=await fetch(p);if(!r.ok)throw Error(r.status);return r.json()}
async function refresh(){try{
const [o,f,r,j]=await Promise.all([get('/api/overview'),get('/api/finance'),get('/api/records'),get('/api/jobs')]);
document.getElementById('stats').innerHTML=Object.entries(o.records).map(([k,v])=>'<div class="stat"><b>'+v+'</b><small>'+k.replaceAll('_',' ')+'</small></div>').join('');
document.getElementById('finance').textContent=JSON.stringify(f.summary,null,2);
document.getElementById('records').textContent=r.records.slice(0,15).map(x=>'#'+x.id+' · '+x.kind+' · '+x.status+' · '+x.title).join('\n')||'No records yet.';
document.getElementById('jobs').textContent=j.jobs.slice(0,10).map(x=>'#'+x.id+' · '+x.kind+' · '+x.status).join('\n')||'No jobs yet.';
}catch(e){document.getElementById('records').textContent='API unavailable: '+e}}
refresh();setInterval(refresh,5000);
</script></html>""".replace("__VERSION__", __version__)

def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self,status,body,content_type="application/json"):
            data=body.encode() if isinstance(body,str) else json.dumps(body).encode()
            self.send_response(status); self.send_header("Content-Type",content_type+"; charset=utf-8")
            self.send_header("Content-Length",str(len(data))); self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(data)
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
                with connect(db_path) as conn:
                    jobs=conn.execute("SELECT status,COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
                    records=conn.execute("SELECT kind,COUNT(*) AS n FROM workspace_records GROUP BY kind").fetchall()
                return self._send(200,{"jobs":{r["status"]:r["n"] for r in jobs},"records":{r["kind"]:r["n"] for r in records}})
            if path=="/api/jobs": return self._send(200,{"jobs":list_jobs(db_path)})
            if path=="/api/records":
                kind=parse_qs(urlparse(self.path).query).get("kind",[None])[0]
                return self._send(200,{"records":list_records(db_path,kind)})
            if path=="/api/approvals": return self._send(200,{"approvals":list_approvals(db_path)})
            if path=="/api/finance": return self._send(200,{"summary":finance_summary(db_path)})
            return self._send(404,{"error":"not_found"})
        def do_POST(self):
            path=urlparse(self.path).path
            try:
                body=self._body()
                if path=="/api/jobs":
                    job=enqueue(db_path,str(body.get("kind","")),body.get("payload",{}),body.get("idempotency_key"))
                    return self._send(201,{"job":job})
                if path=="/api/records":
                    record=create_record(db_path,body.get("kind"),body.get("title"),body.get("data",{}),body.get("status"))
                    return self._send(201,{"record":record})
                if path=="/api/approvals":
                    approval=request_approval(db_path,body.get("action",""),body.get("target_type",""),body.get("target_id",""),body.get("reason",""),body.get("amount"),body.get("currency"))
                    return self._send(201,{"approval":approval})
                if path.startswith("/api/approvals/") and path.endswith("/decision"):
                    approval_id=int(path.split("/")[3])
                    return self._send(200,{"approval":decide_approval(db_path,approval_id,body.get("decision",""))})
                if path=="/api/finance":
                    entry=add_finance_entry(db_path,body.get("entry_type",""),body.get("amount"),body.get("currency",""),body.get("description",""),body.get("reference"),body.get("actual",False))
                    return self._send(201,{"entry":entry})
                return self._send(404,{"error":"not_found"})
            except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
                return self._send(400,{"error":str(exc)})
        def do_PATCH(self):
            path=urlparse(self.path).path
            if path.startswith("/api/records/"):
                try:
                    record_id=int(path.split("/")[3]); body=self._body()
                    return self._send(200,{"record":transition_record(db_path,record_id,body.get("status",""))})
                except (ValueError,TypeError,json.JSONDecodeError) as exc: return self._send(400,{"error":str(exc)})
            return self._send(404,{"error":"not_found"})
        def log_message(self,fmt,*args): print("[http] "+(fmt%args))
    return Handler

def serve(host,port,db_path):
    if host not in {"127.0.0.1","localhost","::1"}: raise ValueError("Aureon currently binds to localhost only")
    initialize(db_path); initialize_workspace(db_path)
    recovered=recover_interrupted(db_path)
    if recovered["requeued"] or recovered["failed"]: print("Recovered interrupted jobs:",recovered)
    server=ThreadingHTTPServer((host,port),make_handler(db_path))
    print("Aureon: http://%s:%s (mock mode; Ctrl+C to stop)"%(host,port))
    try: server.serve_forever()
    finally: server.server_close()
