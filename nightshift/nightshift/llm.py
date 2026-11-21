"""Optional: drive the crew with a real model through any OpenAI-compatible endpoint.

    export OPENAI_BASE_URL=https://api.groq.com/openai/v1   # or Gemini's OpenAI endpoint, Ollama, ...
    export OPENAI_API_KEY=...
    export NIGHTSHIFT_MODEL=llama-3.3-70b-versatile
    python -m nightshift bench --quick --llm

The model sees the page, the briefing Triage built from Meko (if any) and the transcript so far, and
answers with one JSON step. Same tools, same sandbox, same scoring as the deterministic policy.
If the model returns something unusable, the step falls back to the policy so a run never stalls.
"""
import json
import os
import urllib.request

from .brain import PolicyBrain
from .sandbox import ACTIONS, DIAGNOSTICS

SYSTEM = """You are the on-call engineer for Meridian, an e-commerce stack on YugabyteDB.
Resolve the page with as few steps as possible. Reply with ONE JSON object and nothing else:
{"type":"diagnose","tool":"<name>","why":"..."} or {"type":"act","action":"<name>","args":{...},"why":"..."}
Rules: confirm a remembered fix with one diagnostic before applying it; if live evidence contradicts
memory, trust the evidence; never repeat a known dead end; run a required precondition first.
Diagnostics: %s
Actions: %s""" % (
    "; ".join(f"{n} ({d})" for n, _, d in DIAGNOSTICS),
    "; ".join(f"{n} ({d})" for n, d in ACTIONS.items()),
)


class LLMBrain(PolicyBrain):
    name = "llm"

    def __init__(self):
        super().__init__()
        self.base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.key = os.environ.get("OPENAI_API_KEY", "")
        self.model = os.environ.get("NIGHTSHIFT_MODEL", "gpt-4o-mini")
        self.transcript = []
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def reset(self, view, briefing):
        super().reset(view, briefing)
        self.transcript = []

    def next(self, last=None):
        fallback = super().next(last)  # keeps policy state in sync and is the safety net
        if last:
            obs = last.get("output") or f"{'OK' if last.get('ok') else 'FAILED'}: {last.get('message')}"
            self.transcript.append(f"RESULT of {last.get('tool') or last.get('action')}: {obs}")
        user = f"PAGE on {self.view['service']}: {self.view['alert']}\n"
        if self.brief and self.brief.text:
            user += "\nWhat earlier shifts wrote to shared memory (Meko):\n" + self.brief.text + "\n"
        user += "\n" + "\n".join(self.transcript[-12:]) + "\nNext step as JSON:"
        try:
            step = self._chat(user)
            if step.get("type") == "diagnose" and step.get("tool") in {n for n, _, _ in DIAGNOSTICS}:
                out = {"type": "diagnose", "tool": step["tool"], "why": step.get("why", "")}
            elif step.get("type") == "act" and step.get("action") in ACTIONS and isinstance(step.get("args") or {}, dict):
                out = {"type": "act", "action": step["action"], "args": step.get("args") or {}, "why": step.get("why", ""), "is_fix": True}
            else:
                return fallback
            if fallback.get("type") == "act" and (out["type"] != "act" or (out["action"], out["args"]) != (fallback["action"], fallback["args"])):
                self.queue.insert(0, fallback)  # the model chose something else: keep the policy's step pending
            self.transcript.append(f"STEP: {json.dumps(out)}")
            return out
        except Exception:
            return fallback

    def _chat(self, user):
        body = {"model": self.model, "temperature": 0, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
        req = urllib.request.Request(self.base + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        res = json.loads(urllib.request.urlopen(req, timeout=120).read())
        for k in self.usage:
            self.usage[k] += (res.get("usage") or {}).get(k, 0)
        text = res["choices"][0]["message"]["content"].strip()
        return json.loads(text[text.find("{") : text.rfind("}") + 1])
