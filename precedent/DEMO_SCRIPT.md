# Precedent recording script · 4:20 maximum

Record the live Forge installation, not the standalone fixtures. Replace PAY-412
in the lines below with the target key printed by the seed script. Display the
real key consistently in Rovo and MCP. Rehearse once; leave a few seconds of slack
inside each shot. If an optional capability is unavailable, omit it rather than
present a mock as a live result.

## Setup before recording

- Use free [OBS Studio](https://obsproject.com/), 1920×1080 canvas/output, 30fps,
  browser/window capture and a microphone. Record MKV, then remux to MP4 in OBS.
- Use 100% browser zoom initially; adjust to 110–125% if text is too small at
  1080p. Keep that zoom fixed. Collapse the Jira sidebar if it crowds the panel.
- Seed an otherwise clean site. Keep only the target issue, ledger, Rovo and
  optional MCP client tabs open. Finish authorization prompts in advance.
- Begin with no accepted ledger decision for the target: expected score 67.
  Do not delete real team decisions to stage this; use a fresh demo site/project.
- Check the three precedents have resolutions and the ADR appears after indexing.
  Set Rovo to Precedent, not a generic chat. Prepare the actual MCP endpoint.
- Hide account emails, API tokens, terminal history, notifications and unrelated
  workspaces. Do not record token setup. Use no music or third-party assets you
  lack permission to use. If the site needs time to respond, trim waits, not results.

## Timed shot list and exact voiceover

| Time | Screen and action | Voiceover |
| --- | --- | --- |
| 0:00–0:20 | Target issue summary, then open Precedent panel | “A payment retry looks like a small change. But what if this team already shipped it once, and customers were charged twice? I built Precedent to bring that history into Jira before the next release.” |
| 0:20–0:50 | Score and grade; expand unresolved blocker and past failures | “This is a real Forge issue panel. Ship confidence starts at one hundred and applies visible rules. This issue has an unresolved blocker and three similar past failures. The score is sixty-seven: caution. It is a review signal, not permission to deploy.” |
| 0:50–1:15 | Scroll to precedents; open double-charge issue in prepared tab, return | “The first precedent is a double-charge incident after an authorization timeout. I can follow the source and check what happened. These results are ranked by shared keywords, not generated as a plausible story.” |
| 1:15–1:35 | ADR card; follow Confluence source, return | “The decision page explains the constraint: one checkout, one idempotency key. A timeout does not mean the first authorization failed. That is the context this change needs.” |
| 1:35–2:05 | Record decision inline; paste prepared title/decision/rationale; save | “I will record the team's decision to reuse the original key, and why. Precedent stores the reasoning with this issue. An accepted linked decision adds five points, taking this clean demo to seventy-two. The blocker still needs to be resolved.” |
| 2:05–2:35 | Project Decision Ledger; search idempotency; select card and show details | “The project ledger keeps that reasoning searchable. I can see the decision and its rationale here. If the team changes direction, the author can link an accepted replacement. Superseding preserves the original instead of rewriting history.” |
| 2:35–3:15 | Rovo Chat → Precedent; starter “Assess this issue's ship readiness”; supply actual key; show returned factors/sources. Briefly show starter list. | “The same operations are available to my Rovo agent. I choose the readiness conversation starter and give it the issue key. It retrieves the evidence and explains the factors. The other starters find prior work and relevant decisions. Before recording through chat, the agent is instructed to ask me to confirm the exact text.” |
| 3:15–3:45 | Optional: third-party client already connected by OAuth; call get-issue-precedent for same key, then assess-ship-readiness | “I also expose these four actions through Atlassian MCP. This third-party client uses the same evidence backend. An administrator enables tool exposure, and the user consents through OAuth. The client's access still follows that user's permissions.” |
| 3:45–4:05 | People tab; Graph context if returned, otherwise visible warning | “People with context come from similar Jira work. I also request the assignee's assigned work from Teamwork Graph. That API is Preview. When it is unavailable, Precedent says so and keeps the core evidence usable.” |
| 4:05–4:20 | Return to panel with factor evidence open; end on app name | “I built Precedent so a team does not have to relearn the same lesson at release time. Find what happened, inspect the reasoning, and leave a decision the next person can use.” |

If the MCP segment is unavailable, cut 3:15–3:45 entirely and finish at 3:50. Do not
use the optional segment to claim a connection that has not succeeded. If live
scores differ, investigate the factors before recording; never narrate a false value.

## Public YouTube upload

1. Upload the final video at [YouTube Studio](https://studio.youtube.com/).
2. Title: **Precedent | Before you ship | Codegeist 2026**
3. Description (replace placeholders):

   > I’m Rayhan, the solo builder of Precedent for Codegeist 2026, Apps for Software
   > Teams. This Forge app brings prior Jira incidents, Confluence decisions and
   > explainable ship confidence into the issue under review. It includes a decision
   > ledger, a Rovo agent and Atlassian MCP tools. Teamwork Graph is optional Preview
   > context. The score is a heuristic, not a release guarantee.
   >
   > Install: <INSTALL_LINK>
   > Source: https://github.com/ray3242/money-plays/tree/main/precedent

4. Set visibility to **Public**, not Unlisted or Private. Choose the accurate audience
   setting (this developer demo is not made for children), add captions or review
   automatic captions, and wait for 1080p processing.
5. Open the public URL while signed out. Confirm audio, legible text, total runtime
   under 4:30, correct links and no secrets. Paste the URL into SUBMISSION.md/Devpost.
