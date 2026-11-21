"""End-to-end test against a mock marketplace and a local test site. Run: python3 -m unittest -v"""
import gzip
import json
import os
import socket
import sys
import threading
import time
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
import run  # noqa: E402
from audit import UnsafeUrl, audit, blocks_everything, check_public, extract_url  # noqa: E402
from market import Market  # noqa: E402

PAGE = b"""<!doctype html><html><head><title>Shop</title></head><body>
<h1>One</h1><h1>Two</h1><h4>Skip</h4><img src="a.png"><img src="b.png" alt="b">
<input type="text" id="q"><a href="/ok">ok</a><a href="/missing">gone</a>
<script src="http://insecure.example/x.js"></script></body></html>"""


class Site(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path in ("/", "/ok"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(PAGE)
        elif self.path == "/gz":
            html = b"<html lang='en'><head><title>Compressed page</title></head><body>" + b"<p>word</p>" * 3000 + b"</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            if "gzip" in self.headers.get("Accept-Encoding", ""):
                html = gzip.compress(html)
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(html)
        elif self.path in ("/based", "/forms"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(b'<html><head><title>T</title><base href="/assets/"></head><body><a href="ok">ok</a>'
                                 b'<label>Email <input name="e"></label><label>Size <select name="s"></select></label>'
                                 b'<label>Note <textarea name="n"></textarea></label><label for="x">X</label><input id="x"></body></html>')
        elif self.path == "/assets/ok":
            self.send_response(200)
            self.end_headers()
        elif self.path == "/badlink":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(b'<html><head><title>T</title></head><body><a href="http://[bad">x</a><a href="/ok">ok</a></body></html>')
        else:
            self.send_response(404)
            self.end_headers()


class MarketMock(BaseHTTPRequestHandler):
    state = None

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        s = self.state
        if self.headers.get("Authorization") != "Bearer aat_test":
            return self._send({"error": "unauthorized"}, 401)
        if self.path == "/v1/agents/me/assignments":
            return self._send({"assignments": s["rows"]})
        if self.path.startswith("/v1/assignments/") and "/messages" in self.path:
            aid = self.path.split("/")[3]
            return self._send({"messages": list(reversed(s["threads"].get(aid, []))), "total": 0})
        if self.path.startswith("/v1/jobs/board"):
            return self._send({"jobs": s["board"]})
        self._send({}, 404)

    def do_POST(self):
        s = self.state
        parts = self.path.split("/")
        body = self._body()
        if parts[2] == "assignments":
            aid, action = parts[3], parts[4]
            if action == "start":
                s["started"].append(aid)
            elif action == "messages":
                s["threads"].setdefault(aid, []).append({"body": body["body"], "senderAgentId": "agent"})
            elif action == "submit":
                s["submitted"][aid] = body["deliverableMarkdown"]
            return self._send({})
        if parts[2] == "jobs" and parts[4] == "bids":
            s["bids"][parts[3]] = body
            return self._send({})
        self._send({}, 404)


def serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def row(aid, desc, **kw):
    a = {"assignmentId": aid, "status": "in_progress", "startedAt": None, "submittedAt": None, "deliverableUrl": None}
    a.update(kw)
    return {"assignment": a, "job": {"title": "Job", "description": desc}, "latestMessage": None}


class AgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site, cls.site_url = serve(Site)
        cls.mock, cls.mock_url = serve(MarketMock)

    def setUp(self):
        MarketMock.state = {"rows": [], "threads": {}, "started": [], "submitted": {}, "bids": {}, "board": []}
        self.s = MarketMock.state
        self.m = Market("aat_test", self.mock_url)

    def test_extract_url(self):
        self.assertEqual(extract_url("Audit https://a.io/x, please."), "https://a.io/x")
        self.assertEqual(extract_url("check shop.example.com/pricing now"), "https://shop.example.com/pricing")
        self.assertIsNone(extract_url("audit my site"))
        self.assertEqual(extract_url("see https://en.wikipedia.org/wiki/Rust_(language)."), "https://en.wikipedia.org/wiki/Rust_(language)")
        self.assertEqual(extract_url("(https://a.io/x)"), "https://a.io/x")
        self.assertEqual(extract_url("audit shop.example.com:8443 today"), "https://shop.example.com:8443")
        self.assertEqual(extract_url("audit example.com?ref=1"), "https://example.com?ref=1")
        self.assertIsNone(extract_url("Audit my site, reply to owner@example.com"))
        self.assertEqual(extract_url("mail me@x.com about shop.io/a"), "https://shop.io/a")

    def test_private_addresses_refused(self):
        for u in ("http://127.0.0.1/", "http://169.254.169.254/latest", "file:///etc/passwd", "http://localhost:8080"):
            with self.assertRaises(UnsafeUrl):
                check_public(u)

    def test_audit_findings(self):
        md, summary = audit(self.site_url + "/", allow_private=True)
        for needle in ("no meta description", "2 `<h1>` headings", "1 of 2 images have no `alt`", "no viewport",
                       "1 form field(s) have no label", "served over plain HTTP", "1 of 2 checked links are broken",
                       "/missing", "load over http://", "Heading levels skip", "Fix these first"):
            self.assertIn(needle, md)
        self.assertIn("score", summary)

    def test_job_is_started_and_delivered(self):
        self.s["rows"] = [row("a1", f"Please audit {self.site_url}/")]
        self.assertEqual(run.handle(self.m, self.s["rows"][0], allow_private=True), "submitted")
        self.assertEqual(self.s["started"], ["a1"])
        self.assertIn("# Website audit", self.s["submitted"]["a1"])

    def test_missing_url_asks_once_then_uses_reply(self):
        r = row("a2", "audit my site")
        self.assertEqual(run.handle(self.m, r, allow_private=True), "waiting")
        self.assertEqual(run.handle(self.m, r, allow_private=True), "waiting")
        self.assertEqual(len(self.s["threads"]["a2"]), 1)
        self.assertEqual(self.s["started"], [])
        self.s["threads"]["a2"].append({"body": f"it is {self.site_url}/", "senderAgentId": None})
        self.assertEqual(run.handle(self.m, r, allow_private=True), "submitted")

    def test_private_url_gets_an_honest_deliverable(self):
        self.assertEqual(run.handle(self.m, row("a3", "audit http://127.0.0.1:1/")), "submitted")
        self.assertIn("not possible", self.s["submitted"]["a3"])

    def test_finished_rows_are_skipped(self):
        self.assertEqual(run.handle(self.m, row("a4", "audit https://x.io", status="submitted")), "skip")

    def test_rework_uses_url_from_feedback(self):
        r = row("a5", "audit https://old.example", submittedAt="2026-01-01T00:00:00Z", startedAt="2026-01-01T00:00:00Z")
        r["latestMessage"] = {"body": f"wrong page, use {self.site_url}/ok"}
        run.handle(self.m, r, allow_private=True)
        self.assertIn("/ok", self.s["submitted"]["a5"])

    def test_buyer_correction_before_first_delivery_wins(self):
        r = row("a6", "audit https://old.example")
        r["latestMessage"] = {"body": f"Correction: audit {self.site_url}/ok", "senderSide": "buyer"}
        run.handle(self.m, r, allow_private=True)
        self.assertIn("/ok", self.s["submitted"]["a6"])

    def test_worker_message_does_not_override_brief(self):
        r = row("a7", f"audit {self.site_url}/ok")
        r["latestMessage"] = {"body": "I will audit https://elsewhere.example", "senderSide": "worker"}
        run.handle(self.m, r, allow_private=True)
        self.assertIn("/ok", self.s["submitted"]["a7"])

    def test_compressed_page_is_decoded_and_not_flagged(self):
        md, _ = audit(self.site_url + "/gz", allow_private=True)
        self.assertNotIn("sent uncompressed", md)
        self.assertIn("| Compression | gzip", md)
        self.assertIn("Compressed page", md)

    def test_base_href_and_wrapping_labels(self):
        md, _ = audit(self.site_url + "/based", allow_private=True)
        self.assertIn("| Links found / checked | 1 / 1 |", md)
        self.assertNotIn("checked links are broken", md)
        self.assertNotIn("have no label", md)

    def test_multi_member_gzip_is_fully_decoded(self):
        import audit as A
        data = gzip.compress(b"<h1>one</h1>") + gzip.compress(b"<h2>two</h2>")
        inf = A._decoder("gzip")
        out = b"".join(inf.feed(data[i:i + 7], 10_000) for i in range(0, len(data), 7))
        self.assertEqual(out, b"<h1>one</h1><h2>two</h2>")
        self.assertEqual(A._decoder("gzip").feed(gzip.compress(b"x" * 5000), 100), b"x" * 100)

    def test_robots_groups(self):
        self.assertFalse(blocks_everything("User-agent: *\nDisallow: /admin\n\nUser-agent: BadBot\nDisallow: /\n"))
        self.assertTrue(blocks_everything("User-agent: BadBot\nUser-agent: *\nDisallow: /\n"))
        self.assertTrue(blocks_everything("user-agent: *  # all\ndisallow: /\n"))
        self.assertFalse(blocks_everything("User-agent: *\nDisallow:\n"))

    def test_bids_only_on_matching_jobs(self):
        self.s["board"] = [
            {"jobId": "j1", "title": "SEO audit", "description": "audit https://shop.io", "budgetToken": "USDC", "budgetAmount": "10"},
            {"jobId": "j2", "title": "Write a poem", "description": "about https://shop.io", "budgetToken": "USDC"},
            {"jobId": "j3", "title": "SEO audit", "description": "audit https://shop.io", "budgetToken": "USD"},
            {"jobId": "j4", "title": "SEO audit", "description": "https://shop.io", "budgetToken": "USDC", "minBuilderVerification": "identity"},
            {"jobId": "j5", "title": "SEO audit", "description": "https://shop.io", "jobKind": "competition"},
            {"jobId": "j6", "title": "SEO audit", "description": "https://shop.io", "budgetToken": "USDC", "budgetAmount": "1"},
            {"jobId": "j7", "title": "Smart contract audit", "description": "audit https://github.com/x/y", "budgetToken": "USDC"},
            {"jobId": "j8", "title": "Security audit", "description": "audit the code at https://github.com/x/y", "budgetToken": "USDC"},
        ]
        run.maybe_bid(self.m, set())
        self.assertEqual(list(self.s["bids"]), ["j1"])
        self.assertEqual(self.s["bids"]["j1"]["amount"], "3.00")


    def test_connection_uses_the_vetted_address(self):
        import audit as A
        calls = []

        def rebinding(host, port, *a, **k):
            calls.append(host)
            ip = "93.184.216.34" if len(calls) == 1 else "127.0.0.1"
            return [(2, 1, 6, "", (ip, port))]

        port = int(self.site_url.rsplit(":", 1)[1])
        with mock.patch.object(A.socket, "getaddrinfo", rebinding):
            with self.assertRaises(UnsafeUrl):
                A.fetch(f"http://rebind.test:{port}/")

    def test_stalling_server_is_cut_off(self):
        import audit as A
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        with mock.patch.object(A, "FETCH_DEADLINE", 1):
            t0 = time.time()
            with self.assertRaises(TimeoutError):
                A.fetch(f"http://127.0.0.1:{srv.getsockname()[1]}/", allow_private=True)
            self.assertLess(time.time() - t0, 5)
        srv.close()

    def test_malformed_link_does_not_abort_audit(self):
        md, summary = audit(self.site_url + "/badlink", allow_private=True)
        self.assertIn("score", summary)


if __name__ == "__main__":
    unittest.main()
