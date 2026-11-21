"""Live dashboard: a tiny standard-library HTTP server that streams the crew's events."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .bench import run_story
from .meko import Meko

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
STATE = {"events": [], "running": False, "datapack": None, "meko_url": None, "error": None, "summary": None}
LOCK = threading.Lock()


def _run(args, quick, pace):
    try:
        m = Meko(url=args.meko_url, api_key=args.api_key).connect()
        name = getattr(args, "datapack", None) or f"nightshift-{int(time.time())}"
        m.ensure_datapack(name)
        with LOCK:
            STATE.update(datapack=name, meko_url=m.url)

        def emit(e):
            with LOCK:
                STATE["events"].append(e)

        out = run_story(m, emit=emit, pace=pace, quick=quick)
        STATE["summary"] = out["summary"]
    except Exception as e:  # surfaced in the UI
        STATE["error"] = str(e)
    finally:
        STATE["running"] = False


class H(BaseHTTPRequestHandler):
    args = None

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/state":
            return self._json({"live": True, "running": STATE["running"], "datapack": STATE["datapack"], "meko_url": STATE["meko_url"], "error": STATE["error"], "n": len(STATE["events"])})
        if u.path == "/api/events":
            since = int(q.get("since", ["0"])[0])
            with LOCK:
                ev = STATE["events"][since:]
            return self._json({"events": ev, "running": STATE["running"], "error": STATE["error"], "datapack": STATE["datapack"]})
        name = "index.html" if u.path in ("/", "") else os.path.basename(u.path)
        path = os.path.join(WEB, name)
        if not os.path.isfile(path):
            return self._json({"error": "not found"}, 404)
        body = open(path, "rb").read()
        ctype = {"html": "text/html; charset=utf-8", "json": "application/json", "js": "text/javascript", "css": "text/css", "svg": "image/svg+xml"}.get(name.rsplit(".", 1)[-1], "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/run":
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                return self._json({"ok": False, "error": "cross-origin request refused"}, 403)
            with LOCK:
                if STATE["running"]:
                    return self._json({"ok": False, "error": "already running"}, 409)
                STATE.update(running=True, events=[], datapack=None, error=None, summary=None)
            quick = q.get("quick", ["0"])[0] == "1"
            pace = float(q.get("pace", ["0.25"])[0])
            threading.Thread(target=_run, args=(self.args, quick, pace), daemon=True).start()
            return self._json({"ok": True})
        return self._json({"error": "not found"}, 404)


def serve(args):
    H.args = args
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: the dashboard has no authentication. Anyone who can reach this address can start runs with your Meko credentials and read recalled memory.")
    srv = ThreadingHTTPServer((args.host, args.port), H)
    print(f"Nightshift dashboard: http://{args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
