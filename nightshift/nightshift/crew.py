"""The on-call crew: Triage, Investigator, Fixer and Scribe working one incident.

With `meko=None` the crew is amnesiac (the baseline). With a Meko datapack every step is written
as a decision trace, Triage starts from what any earlier shift learned, and Scribe turns a verified
fix into a shared learning for whoever is on call next.
"""
import json
import re
import time
from dataclasses import dataclass, field

from . import tokens
from .brain import PolicyBrain
from .sandbox import ACTIONS, DIAG_SECONDS, Incident, fmt_action, parse_action

# A promoted learning or runbook chunk comes back with a cross-encoder rerank_score (0..1);
# a private memory comes back with a hybrid similarity score. Below these, recall is ignored.
MIN_RERANK = 0.20
MIN_MEMORY = 0.50
MAX_STEPS = 24


@dataclass
class Briefing:
    playbooks: list = field(default_factory=list)
    dead_ends: list = field(default_factory=list)
    guards: dict = field(default_factory=dict)
    hits: list = field(default_factory=list)  # everything recalled, used or not (for the audit trail)
    text: str = ""  # exactly what is put into the agents' context
    query: str = ""
    best: float = 0.0


def learning_text(inc_id, shift, service, alert, evidence, confirm, fix, guard=None, dead_ends=(), replaces=None):
    parts = [
        f"On-call learning from {inc_id} (shift {shift}).",
        f"Service: {service}.",
        f"Symptom: {alert}.",
        f"Root cause evidence: {evidence}.",
        f"Confirm with: {confirm}.",
        f"Fix: {fmt_action(*fix)}.",
    ]
    if guard:
        parts.append(f"Before fix: {fmt_action(*guard)}.")
    if dead_ends:
        parts.append("Dead ends: " + "; ".join(fmt_action(a, g) for a, g in dead_ends) + " did not help.")
    if replaces:
        parts.append(f"Replaces: {fmt_action(*replaces)} no longer works for this service.")
    return " ".join(parts)


_F = {
    "inc": re.compile(r"learning from (INC-\d+) \(shift ([\w-]+)\)"),
    "service": re.compile(r"Service: ([\w.-]+?)\."),
    "confirm": re.compile(r"Confirm with: (\w+)"),
    "fix": re.compile(r"Fix: ([a-z_]+\([^)]*\))"),
    "guard": re.compile(r"Before fix: ([a-z_]+\([^)]*\))"),
    "dead": re.compile(r"Dead ends: (.*?) did not help"),
    "replaces": re.compile(r"Replaces: ([a-z_]+\([^)]*\))"),
    "policy": re.compile(r"Before ([a-z_]+): ([a-z_]+)\("),
}


def parse_learning(text):
    m = _F["fix"].search(text or "")
    if not m or "On-call learning" not in text:
        return None
    out = {"fix": parse_action(m.group(1))}
    i = _F["inc"].search(text)
    out["incident"], out["shift"] = (i.group(1), i.group(2)) if i else ("?", "?")
    for k in ("service", "confirm"):
        mm = _F[k].search(text)
        out[k] = mm.group(1) if mm else None
    g = _F["guard"].search(text)
    out["guard"] = parse_action(g.group(1)) if g else None
    d = _F["dead"].search(text)
    out["dead"] = [a for a in (parse_action(x) for x in d.group(1).split(";")) if a] if d else []
    r = _F["replaces"].search(text)
    out["replaces"] = parse_action(r.group(1)) if r else None
    return out


class Crew:
    def __init__(self, shift, meko=None, brain=None, emit=None, pace=0.0):
        self.shift = shift
        self.meko = meko
        self.brain = brain or PolicyBrain()
        self._emit = emit or (lambda e: None)
        self.pace = pace
        self.t0 = time.time()
        self._threads = {}
        self._inc_meta = {}

    def agent(self, role):
        return f"{self.shift}:{role}"

    def emit(self, inc, role, kind, text, **data):
        ev = {"ts": round(time.time() - self.t0, 3), "incident": inc.id if inc else None, "shift": self.shift, "agent": role, "kind": kind, "text": text}
        ev.update(data)
        self._emit(ev)
        if self.pace:
            time.sleep(self.pace)
        return ev

    # ------------------------------------------------------------------------------ Triage --
    def triage(self, inc, conv):
        m, role = self.meko, "triage"
        query = f"{inc.s.service}: {inc.alert}"
        res = m.context_search(conv, self.agent(role), query, limit=5)
        b = Briefing(query=query)
        learned = []
        for h in res["knowledge_base"]:
            score = h.get("rerank_score") or 0.0
            src = "shared learning" if (h.get("metadata_filters") or {}).get("source") == "memory" else "runbook"
            b.hits.append({"id": h.get("id"), "bucket": "knowledge", "source": src, "score": round(score, 3), "text": h.get("chunk_text", ""), "used": score >= MIN_RERANK,
                           "written_by": (h.get("metadata_filters") or {}).get("agent_id")})
        for h in res["memory"]:
            score = h.get("score") or 0.0
            b.hits.append({"id": h.get("id"), "bucket": "memory", "source": "private memory", "score": round(score, 3), "text": h.get("memory", ""), "used": score >= MIN_MEMORY, "written_by": h.get("agent_id")})
        for h in res["conversation"]:
            b.hits.append({"id": h.get("id") or h.get("conversation_id"), "bucket": "conversation", "source": "past conversation", "score": round(h.get("score") or 0.0, 3), "text": str(h.get("content") or h.get("text") or h.get("input") or h)[:300], "used": False})
        b.best = max([h["score"] for h in b.hits if h["bucket"] == "knowledge"] + [0.0])
        used = [h for h in b.hits if h["used"]]
        for n, h in enumerate(used, 1):
            h["label"] = f"[{n}] {h['source']}"
            cite = {"id": h["id"], "label": h["label"], "score": h["score"], "source": h["source"]}
            L = parse_learning(h["text"])
            if L:
                cite["label"] = f"[{n}] {L['incident']} learning (shift {L['shift']})"
                h["label"] = cite["label"]
                learned.append((L, cite, h))
            for pm in _F["policy"].finditer(h["text"]):
                if not L:
                    b.guards.setdefault(pm.group(1), {"action": pm.group(2), "cite": cite})
        # newer learnings can retire older ones for the same service
        retired = {(L["service"], L["replaces"][0]) for L, _, _ in learned if L["replaces"]}
        for L, cite, h in learned:
            if (L["service"], L["fix"][0]) in retired:
                h["retired"] = True
                continue
            pb = {"action": L["fix"][0], "args": L["fix"][1], "confirm": L["confirm"], "cite": cite, "service": L["service"]}
            if L["guard"]:
                pb["guard"] = {"action": L["guard"][0], "cite": cite}
            b.playbooks.append(pb)
            if L["service"] == inc.s.service:
                for a, g in L["dead"]:
                    b.dead_ends.append({"action": a, "args": g, "cite": cite})
        b.playbooks.sort(key=lambda p: (p["service"] != inc.s.service, -p["cite"]["score"]))
        b.playbooks = b.playbooks[:3]
        b.text = "\n".join(f"{h['label']} (relevance {h['score']}): {h['text']}" for h in used if not h.get("retired"))
        return b

    # ----------------------------------------------------------------------------- run one --
    def handle(self, scenario, alert_variant=0, seed=0, incident_id="INC-0001"):
        inc = Incident(scenario, alert_variant, seed, incident_id)
        m = self.meko
        r = {"incident": inc.id, "scenario": scenario.key, "title": scenario.title, "service": scenario.service, "alert": inc.alert, "shift": self.shift,
             "mode": "meko" if m else "cold", "brain": self.brain.name, "in_tokens": 0, "out_tokens": 0, "recall_tokens": 0, "steps": [], "cites": [], "learned": None}
        self.emit(inc, "pager", "page", inc.alert, service=scenario.service, title=f"{inc.id} on {scenario.service}")
        r["in_tokens"] += tokens.count(inc.alert)

        conv = brief = None
        if m:
            conv = m.conversation(self.agent("triage"), f"{inc.id} {scenario.service}: {inc.alert[:60]}", metadata={"incident": inc.id, "shift": self.shift, "service": scenario.service})
            r["conversation_id"] = conv
            self._inc_meta[conv] = (f"{inc.id} {scenario.service}", {"incident": inc.id, "shift": self.shift, "service": scenario.service})
            brief = self.triage(inc, conv)
            r["recall_tokens"] = tokens.count(brief.text)
            r["in_tokens"] += r["recall_tokens"]
            r["best_match"] = brief.best
            n_used = len([h for h in brief.hits if h["used"]])
            if brief.playbooks:
                summary = f"Recalled {n_used} relevant item(s). Best lead: {brief.playbooks[0]['cite']['label']} -> {fmt_action(brief.playbooks[0]['action'], brief.playbooks[0]['args'])}."
            elif n_used:
                summary = f"Recalled {n_used} relevant item(s) (policy or runbook), but no prior fix for this symptom."
            else:
                summary = "Nothing relevant in shared memory. This looks new: the crew works it from scratch and will write it down."
            self.emit(inc, "triage", "recall", summary, hits=brief.hits, query=brief.query, tokens=r["recall_tokens"],
                      dead_ends=[fmt_action(d["action"], d["args"]) for d in brief.dead_ends], guards={k: v["action"] for k, v in brief.guards.items()})
            self._trace(conv, "triage", f"PAGE {inc.id}: {inc.alert}", summary, reasoning=f"context_search('{brief.query}') returned {len(brief.hits)} hits; kept those above the relevance floor.",
                        plan=[f"confirm with {p['confirm']} then {fmt_action(p['action'], p['args'])}" for p in brief.playbooks] or ["standard diagnostic sweep"],
                        metadata={"cited": [h["id"] for h in brief.hits if h["used"]]})

        brain = self.brain
        brain.reset({"alert": inc.alert, "service": scenario.service, "incident": inc.id}, brief)
        brain.conflict = None
        brain.skipped = []
        brain.unconfirmed = []
        last = None
        fix_step = None
        failed = []
        guard_used = None
        for _ in range(MAX_STEPS):
            step = brain.next(last)
            r["out_tokens"] += tokens.count(step.get("why", "")) + 12
            if step["type"] == "give_up":
                self.emit(inc, "investigator", "stuck", step["why"])
                break
            if step["type"] == "diagnose":
                out = inc.diagnose(step["tool"])
                tk = tokens.count(out)
                r["in_tokens"] += tk
                last = dict(step, output=out)
                hot = _interesting(out, step["tool"], scenario.service)
                self.emit(inc, "investigator", "diagnose", step["why"], tool=step["tool"], tokens=tk, cites=step.get("cites"), finding=hot, seconds=DIAG_SECONDS[step["tool"]])
                r["steps"].append({"agent": "investigator", "type": "diagnose", "tool": step["tool"], "tokens": tk, "why": step["why"]})
                if m:
                    self._trace(conv, "investigator", f"run diagnostic {step['tool']}", hot or "nothing abnormal", reasoning=step["why"], metadata={"tool": step["tool"], "tokens": tk, "cited": [c["id"] for c in step.get("cites") or []]})
            else:
                if m and step.get("is_fix") and not step.get("retry") and not step.get("cites"):
                    g = self.preflight(inc, conv, step, r)
                    if g and g["action"] not in [a["action"] for a in inc.action_calls]:
                        g_args = {k: v for k, v in step["args"].items() if k in ("node", "service")}
                        gres = inc.act(g["action"], g_args)
                        gcall = fmt_action(g["action"], g_args)
                        why = f"{g['cite']['label']} requires {g['action']} before {step['action']}. Doing it first."
                        self.emit(inc, "fixer", "action", why, call=gcall, ok=gres["ok"], result=gres["message"], cites=[g["cite"]])
                        r["steps"].append({"agent": "fixer", "type": "act", "call": gcall, "ok": gres["ok"], "why": why})
                        r["in_tokens"] += tokens.count(gres["message"])
                        self._trace(conv, "fixer", f"apply {gcall}", gres["message"], reasoning=why, metadata={"cited": [g["cite"]["id"]]})
                        if g["cite"] not in r["cites"]:
                            r["cites"].append(g["cite"])
                        if gres["ok"]:
                            guard_used = (g["action"], g_args)
                res = inc.act(step["action"], step["args"])
                tk = tokens.count(res["message"])
                r["in_tokens"] += tk
                last = dict(step, ok=res["ok"], message=res["message"])
                call = fmt_action(step["action"], step["args"])
                self.emit(inc, "fixer", "action", step["why"], call=call, ok=res["ok"], result=res["message"], cites=step.get("cites"), contradicts=step.get("contradicts"))
                r["steps"].append({"agent": "fixer", "type": "act", "call": call, "ok": res["ok"], "why": step["why"]})
                if m:
                    self._trace(conv, "fixer", f"apply {call}", ("OK: " if res["ok"] else "FAILED: ") + res["message"], reasoning=step["why"],
                                metadata={"action": step["action"], "ok": res["ok"], "cited": [c["id"] for c in step.get("cites") or []]})
                for c in step.get("cites") or []:
                    if c not in r["cites"]:
                        r["cites"].append(c)
                if res["ok"] and inc.resolved:
                    fix_step = step
                    break
                if res["ok"]:
                    guard_used = (step["action"], step["args"])
                elif not step.get("retry") and "refused" not in res["message"]:
                    failed.append((step["action"], step["args"]))
                elif "refused" in res["message"] and "no longer" in res["message"]:
                    failed.append((step["action"], step["args"]))

        r.update(resolved=inc.resolved, diagnostics=len(inc.diag_calls), actions=len(inc.action_calls), failed_actions=inc.failed_actions, mttr_seconds=inc.sim_seconds,
                 tokens=r["in_tokens"] + r["out_tokens"], skipped_dead_ends=[fmt_action(h[0], h[1]) for h in brain.skipped])
        self.emit(inc, "pager", "resolved" if inc.resolved else "unresolved", inc.health(), tokens=r["tokens"], mttr_seconds=inc.sim_seconds, failed_actions=inc.failed_actions, diagnostics=len(inc.diag_calls))

        if m:
            self.scribe(inc, conv, r, brain, fix_step, failed, guard_used, last)
        return r

    def preflight(self, inc, conv, step, r):
        """Fixer's pre-flight: before changing production, ask shared knowledge whether this
        organisation has a rule about this exact action."""
        action = step["action"]
        if any(s.get("call", "").startswith(action + "(") for s in r["steps"]):
            return None
        hits = self.meko.kb_search(self._thread(conv, "fixer"), self.agent("fixer"), f"change policy for {action}: precondition before {action}", limit=2)
        for h in hits:
            score = h.get("rerank_score") or 0.0
            text = h.get("chunk_text", "")
            if score < MIN_RERANK or parse_learning(text):
                continue
            for pm in _F["policy"].finditer(text):
                if pm.group(1) == action:
                    tk = tokens.count(text)
                    r["in_tokens"] += tk
                    r["recall_tokens"] += tk
                    cite = {"id": h.get("id"), "label": "runbook: change policy", "score": round(score, 3), "source": "runbook"}
                    self.emit(inc, "fixer", "preflight", f"Pre-flight check for {action}: the change policy runbook says to run {pm.group(2)} first.", tokens=tk,
                              hits=[{"id": h.get("id"), "bucket": "knowledge", "source": "runbook", "score": round(score, 3), "text": text, "used": True, "label": cite["label"]}])
                    return {"action": pm.group(2), "cite": cite}
        return None

    # ------------------------------------------------------------------------------ Scribe --
    def scribe(self, inc, conv, r, brain, fix_step, failed, guard_used, last):
        m, role = self.meko, "scribe"
        who = self.agent(role)
        reused = bool(fix_step and fix_step.get("cites")) and not brain.conflict

        def spend(text):  # writing memory costs tokens too, so it counts toward the incident
            tk = tokens.count(text)
            r["out_tokens"] += tk
            r["tokens"] += tk
        if inc.resolved and not reused:
            confirm = next((s["tool"] for s in reversed(r["steps"]) if s["type"] == "diagnose"), "metrics")
            replaces = None
            if brain.conflict and brain.conflict["memory"].get("service") == inc.s.service:
                c = brain.conflict["memory"]
                replaces = (c["action"], c["args"])
            for a, g in failed:  # a remembered fix that was refused as retired is also replaced
                if any(p["action"] == a for p in (brain.brief.playbooks if brain.brief else [])):
                    replaces = replaces or (a, g)
            dead = [(a, g) for a, g in failed if not replaces or a != replaces[0]]
            text = learning_text(inc.id, self.shift, inc.s.service, inc.alert, fix_step.get("evidence") or last.get("message", ""), confirm,
                                 (fix_step["action"], fix_step["args"]), guard_used, dead, replaces)
            spend(text)
            mid = m.remember(self._thread(conv, role), who, text, {"kind": "learning", "incident": inc.id, "service": inc.s.service, "shift": self.shift})
            self.emit(inc, role, "learn", "Fix verified by the cleared alert. Wrote it down as a private memory.", memory_id=mid, memory=text)
            try:
                m.promote(self._thread(conv, role), who, [mid])
                self.emit(inc, role, "promote", "Promoted the verified learning to the team's shared knowledge: every agent on every shift can now recall it.", memory_id=mid,
                          replaces=fmt_action(*replaces) if replaces else None)
                r["promoted"] = True
                self.verify_recall(inc, conv, r, mid)
            except Exception as e:  # role without promote rights: the memory still exists privately
                self.emit(inc, role, "note", f"Could not promote (kept private): {e}")
            r["learned"] = text
            if replaces:
                r["corrected_memory"] = fmt_action(*replaces)
        elif inc.resolved:
            self.emit(inc, role, "reuse", f"Resolved with {fix_step['cites'][0]['label']}. Nothing new to learn, so nothing new is written: shared memory stays small.", cites=fix_step["cites"])
            r["reused"] = fix_step["cites"][0]["label"]
        else:
            note = f"Open incident {inc.id} on {inc.s.service} (shift {self.shift}): '{inc.alert}' is NOT resolved. Already tried: " + ("; ".join(fmt_action(a, g) for a, g in failed) or "nothing") + "."
            spend(note)
            mid = m.remember(self._thread(conv, role), who, note, {"kind": "handoff", "incident": inc.id})
            self.emit(inc, role, "learn", "Unresolved: left a private handoff note for the next shift (not promoted, because it is not verified).", memory_id=mid, memory=note)

        pm = postmortem(r)
        sconv = self._thread(conv, role)
        art = m.put_artifact(sconv, who, f"{inc.id}-postmortem.md", pm)
        r["postmortem_hash"] = art.get("content_hash")
        self.emit(inc, role, "artifact", f"Postmortem stored as a content-addressed artifact ({art.get('content_hash', '')[:12]}...).", content_hash=art.get("content_hash"), filename=f"{inc.id}-postmortem.md", body=pm)
        m.track_tokens(conv, f"{inc.id} resolution", r["in_tokens"], r["out_tokens"], model=self.brain.model)
        self._trace(conv, role, f"close out {inc.id}", ("resolved" if inc.resolved else "unresolved") + f"; {r['tokens']} tokens, {r['diagnostics']} diagnostics, {r['failed_actions']} failed changes",
                    reasoning="Only a fix verified by the alert clearing is promoted to shared knowledge. Reused fixes are not written twice.",
                    metadata={"postmortem": r["postmortem_hash"], "tokens": r["tokens"], "mttr_seconds": r["mttr_seconds"]})

    def verify_recall(self, inc, conv, r, memory_id, wait=8):
        """Close the loop the way Meko's self-learning does: replay the search that came up short
        and check that the new learning is now what it finds."""
        before = r.get("best_match") or 0.0
        query = f"{inc.s.service}: {inc.alert}"
        after, deadline = 0.0, time.time() + wait
        while time.time() < deadline:
            res = self.meko.kb_search(self._thread(conv, "scribe"), self.agent("scribe"), query, limit=5)
            mine = [h.get("rerank_score") or 0.0 for h in res if (h.get("metadata_filters") or {}).get("memory_id") == memory_id]
            if mine:
                after = max(mine)
                break
            time.sleep(0.5)
        r["recall_before"], r["recall_after"] = round(before, 3), round(after, 3)
        if before < MIN_RERANK:
            msg = f"Replayed the search that came up empty: best match for this page went from {before:.2f} to {after:.2f}. The next shift will find it."
        else:
            msg = f"Replayed this page's search: the new learning now ranks at {after:.2f}, so the next shift gets the right lead first."
        self.emit(inc, "scribe", "verify", msg, before=round(before, 3), after=round(after, 3))

    def _thread(self, conv, role):
        """Meko conversations belong to one agent, so each role keeps its own trace thread per
        incident. All of them carry the same run_id (the triage conversation) and incident id."""
        key = (conv, role)
        if key not in self._threads:
            if role == "triage":
                self._threads[key] = conv
            else:
                title, meta = self._inc_meta.get(conv, ("incident", {}))
                self._threads[key] = self.meko.conversation(self.agent(role), f"{title} [{role}]", metadata=dict(meta, role=role, triage_conversation=conv), run_id=conv)
        return self._threads[key]

    def _trace(self, conv, role, input, output, reasoning=None, plan=None, metadata=None):
        try:
            self.meko.trace(self._thread(conv, role), self.agent(role), input, output[:1200], reasoning=reasoning, plan=plan, metadata=metadata)
        except Exception as e:  # tracing must never take down the on-call path
            self._emit({"ts": round(time.time() - self.t0, 3), "incident": None, "shift": self.shift, "agent": role, "kind": "note", "text": f"trace write failed: {e}"})


def _interesting(output, tool, service):
    from .brain import interpret

    hy = interpret(tool, output, service)
    return "; ".join(h[2] for h in hy) if hy else ""


def postmortem(r):
    L = [f"# Postmortem {r['incident']}: {r['title']}", "", f"- Service: {r['service']}", f"- Alert: {r['alert']}", f"- Shift: {r['shift']} ({r['mode']})",
         f"- Outcome: {'resolved' if r['resolved'] else 'UNRESOLVED'} in {r['mttr_seconds']}s simulated, {r['tokens']} tokens, {r['failed_actions']} failed change(s)", "", "## Timeline"]
    for i, s in enumerate(r["steps"], 1):
        if s["type"] == "diagnose":
            L.append(f"{i}. investigator ran `{s['tool']}` ({s['tokens']} tokens). {s['why']}")
        else:
            L.append(f"{i}. fixer applied `{s['call']}`: {'ok' if s['ok'] else 'FAILED'}. {s['why']}")
    if r.get("cites"):
        L += ["", "## Context this decision relied on"] + [f"- {c['label']} (relevance {c['score']}, id {c['id']})" for c in r["cites"]]
    if r.get("learned"):
        L += ["", "## Learning written to shared memory", r["learned"]]
    return "\n".join(L) + "\n"
