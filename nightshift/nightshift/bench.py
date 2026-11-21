"""Three nights on call, two crews: one amnesiac, one that shares a Meko datapack.

Every shift is a brand-new crew (new agent ids, fresh process state). The only thing that carries
over from one night to the next is what is stored in Meko.
"""
import json
import os
import time

from . import tokens
from .brain import PolicyBrain
from .crew import Crew
from .sandbox import SCENARIOS

BASE = [k for k in SCENARIOS if k not in ("lookalike-slow-query", "pool-exhaustion-migrated")]
SHIFTS = [
    ("alpha", "Night 1", "First time the crew sees any of this.", [(k, 0) for k in BASE]),
    ("bravo", "Night 2", "A different crew. Same faults, worded differently, plus a look-alike.", [(k, 1) for k in BASE] + [("lookalike-slow-query", 0)]),
    ("charlie", "Night 3", "A third crew. The pooler was replaced since night 1, so one remembered fix is stale.",
     [(k, 2) for k in BASE] + [("lookalike-slow-query", 0), ("pool-exhaustion-migrated", 0)]),
]
QUICK = ["pool-exhaustion", "disk-wal", "missing-index", "bad-deploy"]
RUNBOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runbooks")


def seed_runbooks(meko, emit=None):
    conv = meko.conversation("nightshift:setup", "seed runbooks")
    for name in sorted(os.listdir(RUNBOOKS)):
        st = meko.upload_knowledge(conv, os.path.join(RUNBOOKS, name))
        if emit:
            emit({"ts": 0, "incident": None, "shift": "setup", "agent": "setup", "kind": "seed", "text": f"Indexed runbook {name} into the shared knowledge base ({(st or {}).get('state', 'ok')})."})


def run_story(meko, emit=None, pace=0.0, quick=False, brain_factory=PolicyBrain, on_result=None, baseline=True):
    emit = emit or (lambda e: None)
    seed_runbooks(meko, emit)
    results, n = [], 0
    for shift, night, blurb, plan in SHIFTS:
        if quick:
            plan = [p for p in plan if p[0] in QUICK or p[0] not in BASE]
        emit({"ts": 0, "incident": None, "shift": shift, "agent": "pager", "kind": "shift", "text": f"{night}: shift {shift} comes on call. {blurb}", "night": night, "incidents": len(plan)})
        for key, variant in plan:
            n += 1
            inc_id = f"INC-{n:04d}"
            sc = SCENARIOS[key]
            cold = Crew(shift, None, brain_factory()).handle(sc, variant, seed=n, incident_id=inc_id) if baseline else None
            warm = Crew(shift, meko, brain_factory(), emit=emit, pace=pace).handle(sc, variant, seed=n, incident_id=inc_id)
            row = {"incident": inc_id, "night": night, "shift": shift, "scenario": key, "title": sc.title, "service": sc.service, "alert": warm["alert"], "cold": _slim(cold), "meko": _slim(warm)}
            results.append(row)
            emit({"ts": 0, "incident": inc_id, "shift": shift, "agent": "pager", "kind": "score", "text": "", "row": row})
            if on_result:
                on_result(row)
        time.sleep(1.0)  # let promoted learnings finish indexing before the next crew arrives
    return {"results": results, "summary": summarize(results), "token_method": tokens.METHOD, "brain": brain_factory().model}


def _slim(r):
    if not r:
        return None
    keep = ("resolved", "tokens", "in_tokens", "out_tokens", "recall_tokens", "diagnostics", "actions", "failed_actions", "mttr_seconds", "best_match", "reused", "learned",
            "corrected_memory", "recall_before", "recall_after", "skipped_dead_ends", "postmortem_hash", "conversation_id")
    out = {k: r.get(k) for k in keep if r.get(k) is not None}
    out["steps"] = [s.get("tool") or s.get("call") for s in r["steps"]]
    return out


def summarize(results):
    out = []
    for shift, night, _, _ in SHIFTS:
        rows = [r for r in results if r["shift"] == shift]
        if not rows:
            continue
        s = {"night": night, "shift": shift, "incidents": len(rows)}
        for arm in ("cold", "meko"):
            a = [r[arm] for r in rows if r.get(arm)]
            if not a:
                continue
            s[arm] = {"tokens": sum(x["tokens"] for x in a), "diagnostics": sum(x["diagnostics"] for x in a), "failed_actions": sum(x["failed_actions"] for x in a),
                      "mttr_seconds": sum(x["mttr_seconds"] for x in a), "resolved": sum(1 for x in a if x["resolved"])}
        if "cold" in s and s["cold"]["tokens"]:
            s["token_saving_pct"] = round(100 * (1 - s["meko"]["tokens"] / s["cold"]["tokens"]), 1)
            s["mttr_saving_pct"] = round(100 * (1 - s["meko"]["mttr_seconds"] / s["cold"]["mttr_seconds"]), 1)
        m = [r["meko"] for r in rows]
        s["reused"] = sum(1 for x in m if x.get("reused"))
        s["learned"] = sum(1 for x in m if x.get("learned"))
        s["corrected"] = sum(1 for x in m if x.get("corrected_memory"))
        out.append(s)
    return out


def table(summary):
    L = ["| Night | Incidents | Tokens (no memory) | Tokens (Meko) | Saved | Failed prod changes (no memory / Meko) | Time to resolve (no memory / Meko) | Fixes reused | New learnings |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in summary:
        c, m = s.get("cold"), s["meko"]
        L.append(f"| {s['night']} ({s['shift']}) | {s['incidents']} | {c['tokens']:,} | {m['tokens']:,} | {s['token_saving_pct']}% | {c['failed_actions']} / {m['failed_actions']} | "
                 f"{round(c['mttr_seconds'] / 60)} min / {round(m['mttr_seconds'] / 60)} min | {s['reused']} | {s['learned']} |")
    return "\n".join(L)
