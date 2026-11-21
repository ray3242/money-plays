# Delphi evidence-mining playbook

For the agent session that runs the rounds (25 Nov 17:00 UTC to 11 Dec 17:00 UTC). The official guide is `gensyn-delphi-skills/reference/competition.md`; read it again at the start of every session, its changelog says what changed. This file is how we work on top of it.

## Goal and arithmetic

- Rank = total rewards on competition markets. Each market has 20 USDC.e for judgment rewards (paid in arrival order) and 30 for settlement rewards (only if the evidence pointed at the actual outcome).
- To qualify for prizes: at least 10 judged submissions (none of them manipulation) across at least 3 competition markets.
- 3 submissions per market for the whole account, forever. A duplicate or rejected one still uses a slot. A low accepted rate drops the account to 1 per market. So: quality over count, never resend a fact.
- New markets are added every few days. Being early on a new market matters because the judgment pot is shared in arrival order and the first to state a fact wins it.

## Each session

1. `cd gensyn-delphi-skills && npm run evidence -- config` then `-- limits` (what is left this hour and today) and `-- terms` (if `acceptedAt` is null, stop: only Rayhan can accept).
2. `node ../delphi-miner/triage.mjs --used evidence-log.jsonl` for the ranked queue. Take the top markets you have not used up.
3. For each market, before researching: `npm run evidence -- entry-state --market 0x…` (must say `canSubmit: true` and the judgment pot must not be empty) and `-- list --market 0x…` (what this account already sent).
4. Read the resolution criteria word by word and the listed primary source. Write down the exact threshold, date and source that decide Yes or No.
5. Find ONE fact per submission, from the list below. `npm run evidence -- claim --market 0x… --note "…"` before spending time on it.
6. Write the note (template below), save the source as a file when the page needs JavaScript, blocks bots or is a PDF, and submit: `npm run evidence -- submit --market 0x… --note-file note.txt --link https://… --file table.csv`.
7. `npm run evidence -- result --id … --wait`. Record verdict, reward and reason in `results.md`. Adjust: "accepted, no reward" means the forecaster had it, so change the kind of fact, not the wording.
8. Anything broken or unclear in the API or docs: `npm run send-feedback -- --area … --text "…"` with the request id. Five feedback bounties of USD 250 are a separate, much less crowded prize. Aim for a few specific, reproducible reports.

## Where new facts come from (in order of expected value)

1. **A calculation on the primary series.** Download the official table, compute what the next reading must be to cross the market's threshold, and the base rate of that happening. Attach the CSV with inputs and working.
2. **Fresh state in a machine-readable record**: release pipelines and tags, standards-body ballots, court dockets, regulator registers, parliamentary order papers, official gazettes, procurement portals. These move before the news does.
3. **Local-language and niche sources**: regional press, ministry sites, federation sites, mailing lists. Quote the original line and give a translation.
4. **A dated fact from elsewhere that bears on this market**, with one sentence on why.

Never: other prediction markets' or bookmakers' odds, widely reported news, "nothing has changed", a schedule everyone knows, a public live feed, personal data, anything behind a login or against a site's terms, anything invented, any sentence that tells the judge what to conclude.

## Note template (8,000 characters max, one claim)

```
FACT: <the number or state>, as of <date>.
SOURCE: <publisher>, <document or table name>, published <date>, read <date UTC>. <link to the original record>
WHY IT BEARS ON THIS MARKET: the market resolves Yes if <criterion>. This fact means <direction, in one sentence>.
WORKING: inputs <…>; formula <…>; result <…>. Rows are in the attached CSV.
```

## Guard rails

- Do not submit for both Yes and No on one market: settlement value is netted per market.
- Check `RateLimit-Remaining` and the hourly limit; on `429` wait for the reset, never loop.
- Never read `.env`, never print the key, never accept terms for Rayhan.
- Stop at the first `manipulation` verdict and review every pending note before continuing.
