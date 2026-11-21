"""How an agent decides its next step.

PolicyBrain is deterministic: a table of evidence -> remedy rules that stands in for the general
SRE knowledge any competent model already has. It needs no API key, so the benchmark is
reproducible by anyone. LLMBrain (llm.py) plugs a real model into the same interface.

Neither brain knows which incident it is facing. Team-specific knowledge (what worked here last
time, which guardrails this company enforces, which obvious fix is a dead end) only ever arrives
through the briefing that Triage builds from Meko.
"""
import re

from .sandbox import DIAG_ORDER, fmt_action


def _first(regex, text, flags=0):
    return re.search(regex, text, flags)


def interpret(tool, output, service):
    """General knowledge: read one diagnostic output, propose remedies. -> [(action, args, evidence)]"""
    hyps = []

    def add(action, args, m):
        line = next((l.strip() for l in output.splitlines() if m.group(0) in l), m.group(0))
        hyps.append((action, args, line))

    m = _first(r"ysql_conn_mgr.*cl_waiting=(\d{2,})", output)
    if m:
        cur = _first(r"max_server_connections=(\d+)", output)
        add("set_conn_mgr", {"size": int(cur.group(1)) * 4 if cur else 120}, m)
    else:
        m = _first(r"cl_waiting=(\d{2,})", output)
        if m:
            cur = _first(r"default_pool_size=(\d+)", output)
            add("scale_pool", {"size": int(cur.group(1)) * 4 if cur else 80}, m)
    m = _first(r"Seq Scan on (\w+).*index on (\w+)", output)
    if m:
        add("create_index", {"table": m.group(1), "column": m.group(2)}, m)
    m = _first(r"leader balancing DISABLED", output)
    if m:
        add("rebalance_leaders", {}, m)
    m = _first(r"hot tablet: (\w+)", output)
    if m:
        add("split_tablet", {"table": m.group(1)}, m)
    m = _first(r"(yb-node-\d): Too big clock skew", output)
    if m:
        add("sync_clock", {"node": m.group(1)}, m)
    m = _first(r"maxmemory_policy=noeviction", output)
    if m:
        add("set_cache_policy", {"policy": "allkeys-lru"}, m)
    m = _first(r"group (\S+) .*lag=([\d,]{7,}).*members=(\d+)", output)
    if m:
        add("scale_consumers", {"group": m.group(1), "n": int(m.group(3)) * 3}, m)
    m = _first(r"(\S+)\s+EXPIRED", output)
    if m:
        add("renew_cert", {"domain": m.group(1)}, m)
    m = _first(r"(yb-node-\d) /mnt/d0 (9\d|100)% used", output)
    if m:
        add("purge_wal", {"node": m.group(1)}, m)
    m = _first(r"cached, ttl ignored", output)
    if m:
        add("flush_dns", {"service": service}, m)
    m = _first(r"\b([1-5]?\d)m ago\s+flag (\w+) \d+% -> 100%", output)
    if m:
        add("toggle_flag", {"flag": m.group(2), "on": False}, m)
    m = _first(r"restarted \d+ times since deploy", output)
    if m:
        add("rollback", {"service": service}, m)
    m = _first(r"\b([1-5]?\d)m ago\s+deploy (\S+) v", output)
    if m and m.group(2) == service:
        add("rollback", {"service": service}, m)
    m = _first(r"consider restart", output)
    if m:
        add("restart", {"service": service}, m)
    m = _first(r"process restarts in last 6h: [1-9]", output)
    if m:
        add("restart", {"service": service}, m)
    return hyps


def interpret_refusal(message, args, last_outputs):
    """General knowledge: a refused action usually says what it wants first."""
    if "cordon" in message:
        return ("cordon", {"node": args.get("node")}, True)
    if "snapshot" in message:
        return ("snapshot", {"node": args.get("node")}, True)
    if "set_conn_mgr" in message:
        cur = None
        for out in last_outputs:
            cur = cur or _first(r"max_server_connections=(\d+)", out)
        return ("set_conn_mgr", {"size": int(cur.group(1)) * 4 if cur else 120}, False)
    return None


class PolicyBrain:
    name = "policy"
    model = "deterministic-policy"

    def __init__(self):
        self.reset(None, None)

    def reset(self, incident_view, briefing):
        self.view = incident_view  # {"alert":..., "service":...}
        self.brief = briefing  # None when the crew has no Meko
        self.queue = []  # pending steps
        self.seen = {}  # tool -> output
        self.tried = set()
        self.ruled_out = set()  # ids of recalled learnings that live evidence did not confirm
        self.cands = list(briefing.playbooks) if briefing else []
        self.pending_fix = None  # (action, args) waiting for a guard
        self.state = "start"

    # the crew calls this with the result of the previous step
    def next(self, last=None):
        b = self.brief
        if last and last["type"] == "act" and not last["ok"]:
            r = interpret_refusal(last["message"], last["args"], list(self.seen.values()))
            if r and (r[0], _k(r[1])) not in self.tried:
                action, args, then_retry = r
                steps = [_act(action, args, f"The refusal names its precondition, so run {fmt_action(action, args)}" + (" and retry." if then_retry else " instead."))]
                if then_retry:
                    steps.append(_act(last["action"], last["args"], "Precondition met, retrying the fix.", retry=True))
                self.queue = steps + self.queue
        if last and last["type"] == "diagnose":
            self.seen[last["tool"]] = last["output"]
            hyps = interpret(last["tool"], last["output"], self.view["service"])
            cand = last.get("candidate")
            if cand:
                same = [h for h in hyps if h[0] == cand["action"]]
                if not same:
                    self.ruled_out.add(cand["cite"].get("id"))
                other = [h for h in hyps if h[0] != cand["action"] and not self._dead(h)]
                if same:
                    h = same[0]
                    args = h[1] or cand["args"]  # same remedy; parameters come from live evidence
                    self._plan_fix(cand["action"], args, f"Recalled fix confirmed by fresh evidence: {h[2]}", evidence=h[2], cites=[cand["cite"]], guard=cand.get("guard"))
                elif other:
                    h = other[0]
                    self.conflict = {"memory": cand, "evidence": h}
                    self._plan_fix(h[0], h[1], f"Memory suggested {fmt_action(cand['action'], cand['args'])} but the live evidence says otherwise ({h[2]}). Evidence beats memory.", evidence=h[2], contradicts=cand["cite"])
                else:
                    self.unconfirmed = getattr(self, "unconfirmed", []) + [cand]
            else:
                for h in hyps:
                    if self._dead(h):
                        continue
                    self._plan_fix(h[0], h[1], f"Evidence in {last['tool']}: {h[2]}", evidence=h[2])
        if self.queue:
            return self.queue.pop(0)
        # 1) remembered playbooks first: confirm with one targeted diagnostic
        while self.cands:
            c = self.cands.pop(0)
            if (c["action"], _k(c["args"])) in self.tried:
                continue
            tool = c.get("confirm") or "metrics"
            if tool in self.seen:
                hyps = [h for h in interpret(tool, self.seen[tool], self.view["service"]) if h[0] == c["action"]]
                if hyps:
                    self._plan_fix(c["action"], c["args"], f"Recalled fix confirmed by evidence already collected: {hyps[0][2]}", evidence=hyps[0][2], cites=[c["cite"]], guard=c.get("guard"))
                    return self.queue.pop(0)
                self.ruled_out.add(c["cite"].get("id"))
                for h in interpret(tool, self.seen[tool], self.view["service"]):
                    if not self._dead(h):
                        self._plan_fix(h[0], h[1], f"Evidence in {tool}: {h[2]}", evidence=h[2])
                if self.queue:
                    return self.queue.pop(0)
                continue
            return {"type": "diagnose", "tool": tool, "candidate": c, "cites": [c["cite"]],
                    "why": f"{c['cite']['label']} says this symptom was fixed with {fmt_action(c['action'], c['args'])} and can be confirmed with {tool}. Checking before acting."}
        # 2) generic sweep, the way anyone without context would do it
        for tool in DIAG_ORDER:
            if tool not in self.seen:
                return {"type": "diagnose", "tool": tool, "why": "No usable prior context: working through the standard diagnostic sweep."}
        return {"type": "give_up", "why": "All diagnostics read, nothing left to try."}

    def _dead(self, h):
        key = (h[0], _k(h[1]))
        if key in self.tried:
            return True
        # a dead end belongs to the learning that recorded it: once that learning is ruled out
        # for this incident, its dead ends no longer veto what the live evidence points at
        if self.brief and any(d["action"] == h[0] and d["cite"].get("id") not in self.ruled_out for d in self.brief.dead_ends):
            self.skipped = getattr(self, "skipped", []) + [h]
            return True
        return False

    def _plan_fix(self, action, args, why, evidence=None, cites=None, guard=None, contradicts=None):
        key = (action, _k(args))
        if key in self.tried:
            return
        self.tried.add(key)
        guard = guard or (self.brief.guards.get(action) if self.brief else None)
        if guard:
            g_action, g_cite = guard["action"], guard["cite"]
            g_args = {k: v for k, v in args.items() if k in ("node", "service")}
            self.queue.append(_act(g_action, g_args, f"{g_cite['label']} requires {g_action} before {action}. Doing it first.", cites=[g_cite]))
        self.queue.append(_act(action, args, why, evidence=evidence, cites=cites, contradicts=contradicts, is_fix=True))


def _act(action, args, why, **kw):
    d = {"type": "act", "action": action, "args": args, "why": why}
    d.update({k: v for k, v in kw.items() if v})
    return d


def _k(args):
    return tuple(sorted((k, str(v).lower()) for k, v in (args or {}).items()))
