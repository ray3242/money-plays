# Rayhan's account-only handoff

Follow in order. This checkout is locally verified, not deployed. Do not publish
the placeholder app ID or claim bonus integrations before the live smoke test.

## 1. Create accounts and credentials
1. Create a free [Atlassian account](https://id.atlassian.com/signup) and complete
   [Forge getting started](https://developer.atlassian.com/platform/forge/getting-started/).
   Use a development site with both Jira and Confluence. Confirm admin access to
   the products; Rovo availability/entitlements can vary by site.
2. Create an API token at [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
   Use the token type supported by Basic auth against `https://SITE.atlassian.net`
   (an unscoped API token). Scoped tokens may require the API gateway URL, which
   this seed script deliberately does not support. Use a short expiry and revoke
   the seed token when done. Never paste it into source control, chat or video.
3. On your own computer, install Node 22 LTS from [nodejs.org](https://nodejs.org/)
   (includes npm), then install the Forge CLI and clone the repository:
   ```sh
   npm i -g @forge/cli
   git clone https://github.com/ray3242/money-plays
   cd money-plays/precedent
   ```

## 2. Register, build, deploy and provision
1. In the cloned `precedent` directory, run:
   ```sh
   npm ci
   forge login
   forge register Precedent
   ```
   Follow the developer-space prompts. Confirm `manifest.yml` now contains your
   registered app's ARI instead of the all-zero placeholder. Save its UUID for MCP.
   Do not use someone else's app ID.
2. Run:
   ```sh
   npm run build
   npm test
   npm run validate:manifest
   forge lint
   forge deploy --environment development
   forge site provision
   ```
   Provisioning is interactive and has no `--product` or `--site` flag in CLI 15.1.0.
   Repeating it displays the active demo site rather than creating another one.
   Demo sites last 90 days by default; ensure the site remains available throughout
   judging (January 5–February 3, 2027). See the
   [site provision reference](https://developer.atlassian.com/platform/forge/cli-reference/site-provision/).
3. Once provisioning is ready, run:
   ```sh
   forge install --demo-site --product Jira --environment development
   forge install --demo-site --product Confluence --environment development
   ```
   Approve scopes. `--demo-site` (`-d`) is supported; do not combine it with `--site`.
   For a separately created developer site, use `--site YOUR-SITE.atlassian.net`
   instead, once per product. For later scope changes, add `--upgrade`.
   [Install flags](https://developer.atlassian.com/platform/forge/cli-reference/install/).

## 3. Seed the real demo site
1. Use only a disposable development project/space. Have Jira project-admin/create,
   browse/create/assign/transition/link issue permissions and Confluence space/page
   create permissions. Existing projects need Bug and Task issue types and a
   direct transition to a Done-category status that sets a resolution.
2. Run `node scripts/seed-demo.mjs --dry-run` first. It requires no credentials and
   prints only the plan. Then set the environment securely, without echoing tokens:
   ```sh
   export ATLASSIAN_SITE=https://YOUR-DEMO-SITE.atlassian.net
   export ATLASSIAN_EMAIL=YOUR-ATLASSIAN-EMAIL
   read -rs -p 'API token: ' ATLASSIAN_API_TOKEN
   export ATLASSIAN_API_TOKEN
   export PROJECT_KEY=PAY
   export SPACE_KEY=PAY
   node scripts/seed-demo.mjs
   unset ATLASSIAN_API_TOKEN
   ```
   The script does not automatically load `.env`. If the token is scoped or project
   creation is forbidden, use a compatible token or create the project/space in
   the UI; do not weaken the app's runtime permissions to seed data.
3. Note the printed target URL. Jira controls issue numbering: PAY-412 in mock
   screenshots may be PAY-5 on your site. Use the actual key everywhere in the
   recording, Rovo prompts and submission instructions.
4. If the script stops on a workflow/resolution error, configure the workflow to
   set resolution on Done, repair the named issue and rerun. It skips exact existing
   summaries/titles, repairs missing links/labels, and never deletes existing work.
   It does not overwrite existing descriptions. Do not run multiple seeds at once.
5. Open the target issue → Precedent, complete first-use consent and wait for search
   indexing. Verify three resolved precedents, the unresolved blocker and ADR pages.
   Record the idempotency decision using the title/text/rationale in SUBMISSION.md.
   REST cannot seed isolated Forge KVS. A clean score should be 67 before, 72 after.
   Live dates and assignees will differ from the fixture screenshots.

## 4. Enable and test Rovo, MCP and Graph
1. On a Rovo-enabled site, open Rovo Chat and select **Precedent**. Test each
   conversation starter with the actual issue key. Verify citations and warnings.
   Test record-decision only after explicitly confirming title, text and rationale.
   Site/organization admins may need to permit the app/agent in their Rovo policies.
2. For external MCP, a site/org admin must go to **Atlassian Administration → Apps
   → Sites → your site → Connected apps → Precedent → app details** and enable
   the tools to expose. It is off by default and configured per installation.
3. Add `https://mcp.atlassian.com/forge/<APP_UUID>` to a compatible remote MCP client.
   Use only the UUID after `ari:cloud:ecosystem::app/` in the registered manifest.
   Complete OAuth 2.1, choose the site, review tools/scopes and approve access.
   Load `skills/precedent/SKILL.md` into the client's agent instructions. Test a
   read, score, ledger search and an explicitly approved record operation.
   [Official Rovo MCP flow](https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-mcp/).
4. Assign the target issue to a real user and authorize the Graph scopes. Inspect
   People → related work if returned. The implemented query is
   `atlassianUserAssignedJiraWorkItems`; empty/denied results should show a warning.
   Graph and external MCP are Preview. Do not report a fallback as a successful
   Graph call. [Curated queries](https://developer.atlassian.com/platform/teamwork-graph/curated-queries/).

## 5. Generate the judge installation link
1. Run `npm run build`, `forge lint`, then `forge deploy --environment production`.
   Development installations alone cannot provide the public sharing link.
2. Open [Developer Console](https://developer.atlassian.com/console/myapps/), choose
   your registered Precedent app → **Distribution → Distribution controls → Edit**.
3. Select **Sharing**, not “Sharing within organization”, because judges are outside
   your organization. Fill the requested app details and save. Select both Jira
   and Confluence as the supported apps and tell installers to install on both.
4. Copy the generated installation link into `<INSTALL_LINK>` in SUBMISSION.md
   and the video description. This is a console flow, not a CLI “share” command.
5. Test the link with a separate eligible site admin/non-contributor. Verify a
   production installation on both products, consent, panel, ledger and actions.
   Ensure documentation/screenshots match production behavior. Do not submit with
   an untested or contributor-only link.
6. Keep the app unlicensed for installation-link sharing. Apps with a manifest
   license or already submitted for Marketplace listing cannot use this mechanism;
   if pursuing Marketplace too, follow the documented separate unlicensed app-copy
   approach and test that copy's own deployment, ID, endpoint and link.
   [Current sharing instructions](https://developer.atlassian.com/platform/forge/distribute-your-apps/#start-sharing-your-app).

## 6. Record and publish
1. Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md). Record actual installed behavior in OBS,
   at 1080p, under 4:30. Test optional integrations before including those shots.
2. Upload to YouTube with **Public** visibility, wait for HD processing, check it
   signed out, and insert the real `<VIDEO_URL>` in SUBMISSION.md.
3. Publish a source repository if you want to share code/skill. Do not publish
   credentials. The source folder is https://github.com/ray3242/money-plays/tree/main/precedent. The skill has its own
   CC0 license; do not imply all app code has that license unless you choose one.

## 7. Submit to Devpost
1. Create/sign in to a [Devpost account](https://devpost.com/) and join
   [Codegeist 2026](https://codegeist2026.devpost.com/).
2. Review eligibility and [official rules](https://codegeist2026.devpost.com/rules).
   Choose **Apps for Software Teams**; enter as solo entrant Rayhan. Paste the
   fields from SUBMISSION.md, upload screenshots and supply the installation and
   public YouTube URLs. Select only bonus categories actually demonstrated.
3. Replace every placeholder, review the entry preview and complete submission
   **before December 22, 2026, 12:00 noon Pacific** (20:00 UTC). Save the submission
   confirmation. An account or saved draft is not a submitted entry.
4. Keep the app, sharing link and video available throughout judging. Check the
   rules/updates again before submission; current documentation can change.

## 8. Optional fourth bonus: Marketplace
1. Create/associate a Marketplace Partner (vendor) account and review the
   [listing process](https://developer.atlassian.com/platform/marketplace/creating-a-marketplace-listing/).
   Supply the required listing assets, support/privacy details and accept the
   Marketplace Partner Agreement. Paid listings need additional business details.
2. Submit for review; approval is not immediate (documentation estimates 5–10
   business days for an initial response, not guaranteed publication).
3. For the bonus, provide the actual Marketplace listing **or review-ticket URL**,
   as the rules permit. A draft listing, partner account or Forge sharing link
   does not establish this bonus. Resolve the sharing-link restriction in step 5
   before submitting for Marketplace review. Do not claim this bonus yet.

## Final checklist
- [ ] Registered app ID; authenticated lint and live install verified.
- [ ] Real seed, panel, ADR, record, ledger, agent and optional tools smoke-tested.
- [ ] Production Sharing link works for an external admin on both products.
- [ ] App/site remain accessible through February 3, 2027.
- [ ] Public YouTube video works signed out, under 4:30, no secrets.
- [ ] All submission placeholders replaced; bonus claims backed by actual results.
- [ ] Devpost entry submitted before noon PT December 22; confirmation saved.
