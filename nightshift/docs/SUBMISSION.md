# ContextCon submission text (copy-paste)

**Project name:** Nightshift

**Tagline:** On-call agents whose memory survives the shift change.

**Repository:** https://github.com/ray3242/money-plays/tree/main/nightshift

**Live replay:** https://ray3242.github.io/nightshift/

**Demo video (1:48):** https://ray3242.github.io/nightshift/demo.mp4

## Description

At 3 a.m. the pager goes off and whoever is on call starts from zero, even though another shift
fixed this exact fault last week. Agent crews have the same problem, only worse: every run is a new
hire.

Nightshift is a four-agent on-call crew (Triage, Investigator, Fixer, Scribe) working incidents on a
simulated e-commerce stack that runs on a three-node YugabyteDB cluster. Every night a brand-new
crew takes the pager. The only thing that carries over is a shared Meko datapack.

To show what that memory is worth, every incident is run twice: by an identical crew with no memory,
and by the crew on Meko. Over three nights and 39 incidents the Meko crew goes from 8.6% more tokens
on night 1 (writing things down costs something) to 35% fewer on night 2 and 65% fewer on night 3 (memory writes included),
and from 7 failed production changes a night to zero.

## How it uses Meko

Meko is the entire context layer; there is no other store in the repo.

- One shared datapack per rotation; each shift is a new set of agent ids.
- `context_search` is Triage's first move on every page.
- Scribe writes a private memory only after the alert clears, then promotes it to shared knowledge.
- Runbooks live in the knowledge base. Fixer checks it for a change policy before any risky change.
- Every diagnostic and change is a decision trace with its reasoning and the memory it cited.
- Each incident ends with a content-addressed postmortem artifact.

## What is different about it

Shared memory is treated as a lead, not an order. A recalled fix is confirmed against live evidence
before it is applied, so a look-alike incident that recalls the wrong fix at 0.99 relevance still
gets the right one. When the infrastructure changes and a remembered fix goes stale, the crew
notices, applies the right fix, and writes a learning that retires the old one. Only verified fixes
are shared, and a reused fix is never written twice.

## Honest limits

The environment is a simulator and the published numbers use a deterministic policy rather than an
LLM, so anyone can reproduce them for free in about 30 seconds. An optional real-model mode is
included.

## Built with

Python standard library, Meko (MCP over HTTP), YugabyteDB as the modelled system. Built with AI
coding assistance.

# Demo video script (under 5 minutes)

1. (0:00) The problem: one sentence over the dashboard header.
2. (0:20) `python -m nightshift doctor`, then `python -m nightshift serve`, click "Run three nights".
3. (0:45) Night 1: open one incident. Empty recall, full diagnostic sweep, a failed restart, the fix, Scribe's learning and promotion.
4. (1:45) Night 2: a reworded page. Triage's `context_search` hit, one confirming diagnostic, fix. Then the look-alike incident: memory says one thing, evidence another.
5. (2:45) Night 3: the stale pooler fix being retired. The WAL purge with the runbook pre-flight.
6. (3:30) Right-hand panels: tokens per night, failed changes, the shared memory list with reuse counts.
7. (4:00) The Meko UI: the datapack, a decision trace, a postmortem artifact.
8. (4:30) Night 1 costs more; it pays back from night 2. Repo link.
