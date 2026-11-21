# Backend handoff

Run under Node 22 from the monorepo's `precedent` directory. Install with `npm ci`, test with `npm test`, validate with `npm run validate:manifest`.

The manifest's all-zero example app UUID is **not registered**. Replace it through `forge register` with an authenticated account before deploying. Resources currently contain placeholder HTML only; no frontend or live Jira/Confluence installation has been verified. No paid AI calls or external egress are used.

## Contracts

- Resolver `getIssueContext` uses trusted `context.extension.issue.key` and returns `{issue, keywords, issues, pages, decisions, people, graph, warnings, confidence}`.
- `recordDecision` accepts `{title, decision, rationale, tags?, status?, issueKey?}`; issue panel context overrides supplied issue key. Author is always invocation `context.accountId`.
- `listDecisions` accepts `{query?, status?, projectKey?}`, returns `{decisions}`; project page context overrides project filter.
- `supersedeDecision` accepts `{id, byId}`. Only the original author may supersede; replacement must exist and be accepted. Entries linked to inaccessible Jira issues are hidden, including in actions. Unlinked ledger entries are shared within this installation. This author-only mutation policy is a deliberate safety default.
- Rovo functions use top-level payload inputs, return bounded JSON and fail closed on invalid issue keys and inaccessible source issues. Agent prompt asks for confirmation before writes; direct MCP users can invoke CREATE tools, so caller/client consent remains essential (the prompt is not an authorization mechanism).
- Precedent entries have `{key,summary,kind,relevance,url,assignee,resolvedAt}`; people have `{accountId,displayName,count,issueKeys}`. Jira links are site-relative `/browse/KEY`, suitable inside the installed site.

## Limits and uncertainty

Search scans at most 500 ledger entries using KVS cursors, sorts that bounded snapshot newest first, and may omit records beyond the scan. List scans the full ledger, sorts newest first and returns offset cursors; this trades extra reads for correct global ordering because basic KVS queries have no descending-order option. Neither is snapshot-isolated. KVS is eventually consistent; supersede is read-validate-write, not a multi-key transaction. No destructive writes/deletes are exposed. `getIssue` also fetches project statuses to map historical status IDs to Done categories. Scores use available expanded Jira changelog; standard Done/Closed/Resolved names are the fallback when category metadata is unavailable, so deleted custom statuses and truncated histories can undercount reopen events. Display warnings rather than interpreting incomplete evidence as a ship guarantee.

Teamwork Graph uses the documented curated `atlassianUserAssignedJiraWorkItems` query for the current issue's assignee: https://developer.atlassian.com/platform/teamwork-graph/curated-queries/ . Requires user+issue graph scopes. It is optional Preview enrichment. Errors, missing assignee, empty data and missing scope grants are nonfatal. Confluence denial/missing installation is also nonfatal; Jira issue access/search and ledger errors fail closed rather than returning falsely complete evidence.

The backend uses stable npm dist-tags checked during setup: @forge/api 8.5.0, @forge/kvs 2.1.2, @forge/resolver 2.0.2, @forge/manifest 13.9.0. `npm install` reported five moderate transitive advisories; no force upgrades were applied.

## Unauthenticated CLI check

Installed gnome-keyring to remove the VM's missing Secret Service failure. Reproduce the isolated-session probe from this directory with `dbus-run-session -- bash scripts/lint-with-keyring.sh` (after loading nvm). No Atlassian credentials are supplied or stored. See verification results below.

The keyring probe now reaches authentication and fails with `Error: Not logged in. If a local keychain is available, run forge login, otherwise set environment variables before trying again.` Thus `forge lint` still cannot run without credentials. `npm run validate:manifest` is the explicit offline fallback: the JSON schema shipped in @forge/manifest plus local function/action/resource reference and HTML checks. This does not establish registered app validity, deployability, product permissions or live runtime behavior.

The current shipped schema requires descriptions on action inputs, although the public action documentation labels them optional. All declared inputs include descriptions to satisfy the actual installed schema.
