"""Job loop: poll assignments, audit the URL in each brief, submit the report.

Env: AGENT_API_TOKEN (required), RUN_SECONDS (how long to keep polling, default 0 = one pass),
POLL_SECONDS (default 45), AUTO_BID=1 to bid on board jobs that ask for a website audit,
BID_AMOUNT (default 3.00), ACCEPT_USD=1 once Stripe payouts are connected.
"""
import os
import re
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit import UnsafeUrl, audit, extract_url  # noqa: E402
from market import ApiError, Market  # noqa: E402

ASK = ("I audit one web page per job, and I could not find a URL in your brief. "
       "Reply here with the full address (for example https://example.com/pricing) and I will start at once.")
AUDIT_WORDS = re.compile(r"\b(audit|seo|broken links?|accessibility|site (check|review|health)|security headers?)\b", re.I)
PROPOSAL = ("I will audit {url} and deliver a Markdown report within the hour: a 0-100 score, the five fixes to make first, "
            "and every finding with its fix across SEO, security headers, HTTPS, accessibility, performance and broken links. "
            "The checks are deterministic, so the same page always gets the same findings.")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def brief_url(m, row):
    """URL from the job brief, else from the buyer's messages on the thread (newest first)."""
    job = row.get("job") or {}
    url = extract_url(f"{job.get('description', '')}\n{job.get('title', '')}")
    latest = (row.get("latestMessage") or {}).get("body")
    a = row["assignment"]
    if a.get("submittedAt") and latest:  # request-changes: a new URL in the feedback wins
        url = extract_url(latest) or url
    if url:
        return url, False
    asked = False
    for msg in m.messages(a["assignmentId"]):
        if msg.get("senderAgentId"):
            asked = asked or msg.get("body", "").startswith(ASK[:40])
            continue
        url = extract_url(msg.get("body", ""))
        if url:
            return url, asked
    return None, asked


def handle(m, row, allow_private=False):
    a = row["assignment"]
    aid = a["assignmentId"]
    if a.get("status") != "in_progress":
        return "skip"
    url, asked = brief_url(m, row)
    if not url:
        if not asked:
            m.message(aid, ASK)
            log(aid, "asked for a URL")
        return "waiting"
    m.start(aid)  # idempotent
    try:
        report, summary = audit(url, allow_private)
    except UnsafeUrl as e:
        report = (f"# Website audit: not possible\n\nI could not audit `{url}`: {e}.\n\n"
                  "Request changes with a public http(s) address and I will run the audit.\n")
        summary = "could not audit"
    except Exception as e:
        report = (f"# Website audit: the page could not be loaded\n\n`{url}` did not answer: "
                  f"`{type(e).__name__}: {getattr(e, 'reason', e)}`.\n\n"
                  "That is the main finding: visitors and search engines cannot reach this address from the public internet. "
                  "Check the spelling, DNS and that the server is up, then request changes and I will audit it again.\n")
        summary = "page unreachable"
    m.submit(aid, report)
    log(aid, "submitted:", summary)
    return "submitted"


def maybe_bid(m, seen):
    amount = os.environ.get("BID_AMOUNT", "3.00")
    for job in m.board():
        jid = job.get("jobId")
        if not jid or jid in seen or job.get("jobKind") == "competition":
            continue
        seen.add(jid)
        if job.get("minBuilderVerification") not in (None, "", "none"):
            continue
        if job.get("budgetToken") == "USD" and os.environ.get("ACCEPT_USD") != "1":
            continue
        text = f"{job.get('title', '')}\n{job.get('description', '')}"
        url = extract_url(text)
        if not url or not AUDIT_WORDS.search(text):
            continue
        try:
            budget = float(job.get("budgetAmount") or 0)
        except ValueError:
            budget = 0
        if budget and budget < float(amount):
            continue
        try:
            m.bid(jid, amount, PROPOSAL.format(url=url), 3600)
            log("bid on", jid)
        except ApiError as e:
            log("bid refused", jid, e)


def main():
    m = Market()
    end = time.time() + float(os.environ.get("RUN_SECONDS", "0"))
    poll = float(os.environ.get("POLL_SECONDS", "45"))
    seen = set()
    while True:
        try:
            for row in m.assignments():
                try:
                    handle(m, row)
                except Exception:
                    traceback.print_exc()
            if os.environ.get("AUTO_BID") == "1":
                maybe_bid(m, seen)
        except ApiError as e:
            log("poll failed:", e)
            if e.status in (401, 403):
                sys.exit(1)
        if time.time() + poll > end:
            break
        time.sleep(poll)


if __name__ == "__main__":
    main()
