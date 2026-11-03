"""Local-only HTTP control plane."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import __version__
from .db import connect, initialize
from .jobs import enqueue, list_jobs

PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aureon</title><style>
:root{color-scheme:dark;font-family:system-ui;background:#0b1020;color:#e8edf7}
body{max-width:850px;margin:32px auto;padding:0 18px}
header,.stats{display:flex;gap:14px;justify-content:space-between;flex-wrap:wrap}
h1{letter-spacing:-1px}.muted{color:#9aa8bd}
.panel,.stat{background:#121b30;border:1px solid #263650;border-radius:15px;padding:18px;margin:14px 0}
.stat{flex:1;min-width:110px}.stat b{display:block;font-size:25px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#bcd0ee}
</style><header><div><h1>Aureon</h1><span class="muted">Commerce operations · local control plane</span></div>
<span class="muted">v__VERSION__ · MOCK MODE</span></header>
<section class="panel"><h2>Runtime</h2><div class="stats" id="stats">Loading…</div></section>
<section class="panel"><h2>Recent jobs</h2><p class="muted">Durable queue is ready. Domain workers will be added in later milestones.</p><pre id="jobs">Loading…</pre></section>
<script>
async function refresh(){try{
const o=await fetch('/api/overview').then(r=>r.json());
const j=await fetch('/api/jobs').then(r=>r.json());
document.getElementById('stats').innerHTML=['queued','running','failed'].map(function(k){
return '<div class="stat"><b>'+(o.jobs[k]||0)+'</b><span>'+k+'</span></div>';
}).join('');
document.getElementById('jobs').textContent=j.jobs.length?
j.jobs.map(function(x){return '#'+x.id+' · '+x.kind+' · '+x.status;}).join('\\n'):'No jobs yet.';
}catch(e){document.getElementById('jobs').textContent='API unavailable: '+e;}}
refresh();setInterval(refresh,5000);
</script></html>""".replace("__VERSION__", __version__)


def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type="application/json"):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self._send(200, PAGE, "text/html")
            if path == "/health":
                return self._send(200, {"ok": True, "version": __version__, "mode": "mock"})
            if path == "/api/overview":
                with connect(db_path) as conn:
                    rows = conn.execute("SELECT status,COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
                return self._send(200, {"jobs": {r["status"]: r["n"] for r in rows}})
            if path == "/api/jobs":
                return self._send(200, {"jobs": list_jobs(db_path)})
            return self._send(404, {"error": "not_found"})

        def do_POST(self):
            if urlparse(self.path).path != "/api/jobs":
                return self._send(404, {"error": "not_found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 65536:
                    return self._send(413, {"error": "body_size_invalid"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or not isinstance(body.get("payload", {}), dict):
                    return self._send(400, {"error": "expected_object"})
                job = enqueue(db_path, str(body.get("kind", "")), body.get("payload", {}),
                              body.get("idempotency_key"))
                return self._send(201, {"job": job})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._send(400, {"error": str(exc)})

        def log_message(self, fmt, *args):
            print("[http] " + (fmt % args))

    return Handler


def serve(host, port, db_path):
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Aureon currently binds to localhost only")
    initialize(db_path)
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print("Aureon: http://%s:%s (mock mode; Ctrl+C to stop)" % (host, port))
    try:
        server.serve_forever()
    finally:
        server.server_close()
