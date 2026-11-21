# Site Audit agent for the NEAR AI Agent Market

A self-hosted agent for [market.near.ai](https://market.near.ai). A buyer sends a URL; the agent returns a prioritized website audit in Markdown (SEO, security headers, HTTPS, accessibility, performance, broken links) and is paid per job in USDC or USD.

It costs nothing to run: Python standard library only, no AI model, and the job loop runs on GitHub Actions every five minutes.

## How it works

1. `.github/workflows/near-site-audit-agent-poll.yml` (repository root) starts `agent/run.py` every five minutes; each run polls the marketplace for about 4.5 minutes.
2. For each new assignment the agent finds the URL in the brief, declares start, runs `agent/audit.py`, and submits the report.
3. A brief with no URL gets one message asking for it; the job is not started until the buyer replies, so they can still cancel for a full refund.
4. With the repository variable `NEAR_AUTO_BID=1` it also bids (default 3.00) on open board jobs that ask for a website audit and name a URL.

## Set up

1. Sign up at https://market.near.ai (Google sign-in counts as a confirmed email).
2. **Building -> Your agents -> New agent.** Paste the fields from [LISTING.md](LISTING.md). Hosting: **Self-hosted**, webhook empty.
3. Under **Agent API tokens** click **Create token** and copy the `aat_...` value.
4. In the `ray3242/money-plays` repository: **Settings -> Secrets and variables -> Actions -> New repository secret**, name `NEAR_AGENT_API_TOKEN`, value the token.
5. **Actions -> near-site-audit-agent poll -> Run workflow** once, then open `https://market.near.ai/a/site-audit`, click **Test run** and send `Audit https://example.com`. The report should arrive within five minutes.
6. Set **Listing status** to **Live**.
7. To be paid: **Payouts** -> withdraw USDC to a wallet, or connect Stripe for bank payouts in Canada (then set the variable `NEAR_ACCEPT_USD=1`).

Optional repository variables: `NEAR_AUTO_BID=1`, `NEAR_BID_AMOUNT=3.00`, `NEAR_ACCEPT_USD=1`.

## Run locally

```bash
python3 agent/audit.py https://example.com        # print a report
AGENT_API_TOKEN=aat_... python3 agent/run.py      # one pass over your assignments
python3 -m unittest discover -s tests -v          # tests, against a mock marketplace
```

## Limits

- One page per job; JavaScript is not executed.
- Addresses that resolve to private or local networks are refused.
- GitHub pauses scheduled workflows after 60 days without a commit; push any commit to resume.
