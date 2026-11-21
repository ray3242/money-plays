"""Minimal client for the NEAR AI Agent Market worker API (https://market.near.ai/skill/SKILL.md)."""
import json
import os
import urllib.error
import urllib.request


class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


class Market:
    def __init__(self, token=None, base=None):
        self.token = token or os.environ["AGENT_API_TOKEN"]
        self.base = (base or os.environ.get("MARKET_BASE_URL") or "https://market.near.ai").rstrip("/")

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("User-Agent", "SiteAuditAgent/1.0")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                text = res.read().decode()
        except urllib.error.HTTPError as e:
            raise ApiError(e.code, e.read().decode("utf-8", "replace"))
        return json.loads(text) if text else {}

    def assignments(self):
        return self.call("GET", "/v1/agents/me/assignments").get("assignments", [])

    def start(self, aid):
        return self.call("POST", f"/v1/assignments/{aid}/start")

    def messages(self, aid):
        return self.call("GET", f"/v1/assignments/{aid}/messages?limit=20&offset=0").get("messages", [])

    def message(self, aid, body):
        return self.call("POST", f"/v1/assignments/{aid}/messages", {"body": body[:4000]})

    def submit(self, aid, markdown):
        return self.call("POST", f"/v1/assignments/{aid}/submit", {"deliverableMarkdown": markdown})

    def board(self):
        return self.call("GET", "/v1/jobs/board?kind=standard&sort=recent").get("jobs", [])

    def bid(self, job_id, amount, proposal, sla_seconds):
        return self.call("POST", f"/v1/jobs/{job_id}/bids",
                         {"amount": amount, "proposal": proposal, "slaSeconds": sla_seconds})
